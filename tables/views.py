# NOTA TEMPORAL PARA APRENDIZAJE:
# La selección inteligente recuerda por cuenta los tiempos elegidos por este usuario. Al
# completar primero + segundo + guisado/plancha sustituye esas órdenes por un paquete;
# si falta un tiempo, los productos permanecen como órdenes individuales. Borra esta nota.
# Todo el catálogo interno de Mesas ignora horarios; `/pedir/menu/` conserva sus filtros.
# El detalle incorpora cierre y cobro; al concluir conserva el ticket como solo lectura.
# La vista muestra errores amigables, pero el servicio vuelve a validar todo. Borra esta nota.
# El historial separa la consulta de hoy y semana del mapa operativo. Un Mesero ve sus
# cuentas; Administración y Telefonista ven todas. Borra esta nota después de leerla.
# El mapa prepara cada mesa con su cuenta abierta, si existe. Las acciones POST validan
# roles en backend: el Mesero abre para sí mismo; Administración/Telefonista pueden elegir
# responsable, y la reasignación queda limitada a Mesero/Administrador. Borra esta nota.
# El detalle y los diálogos de paquetes responden JSON para actualizar sin recargar.
# El modo de captura se calcula por hora y puede sobrescribirse en la sesión del usuario.
# Esto cambia la interfaz, no la disponibilidad real configurada de productos. Borra la nota.
# Comida por orden se deriva del menú diario y usa un endpoint que vuelve a comprobarlo.
# Los paquetes abiertos conservan y reutilizan el menú de su fecha original al editarse.
# El detalle operativo nunca se guarda en caché: al recargar debe consultar el menú publicado
# del día y no reutilizar el HTML que el navegador mostró ayer. Borra esta nota al leerla.
# Corrida, Ejecutiva y Por orden son nombres reservados: se excluyen del catálogo normal
# en ambos modos y solo se construyen con el menú diario dentro de Modo comida. Borra esta nota.

from datetime import time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, ORDER_TAKER, SECTION_ROLE_MATRIX, WAITER, role_required, user_has_any_role
from config.printing import printable_item, selected_printable_items, table_print_context
from print_station.views import queue_ticket
from menu.inventory import filter_products_by_stock
from menu.egg import egg_products, selected_egg
from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product
from menu.packaging import parse_packaging_quantities
from menu.selection import resolve_product_selection, serialize_product_selector

from .forms import TableAccountCloseForm, TablePackageForm
from .models import DiningTable, TableAccount, TableAccountItem, TableActivity
from .services import add_auto_meal_component, add_daily_menu_product_to_table, add_package_to_table, add_product_to_table, change_item_in_ticket, close_table_account, open_table_account, product_is_available_now, reassign_table_account, record_activity, update_table_package


CAPTURE_MODE_SESSION_KEY = "table_capture_mode"
AUTO_MEAL_SESSION_KEY = "table_auto_meal_builders"
BREAKFAST_MODE = "breakfast"
LUNCH_MODE = "lunch"


def automatic_capture_mode():
    current_time = timezone.localtime().time()
    return BREAKFAST_MODE if time(7, 0) <= current_time < time(13, 0) else LUNCH_MODE


def current_capture_mode(request):
    override = request.session.get(CAPTURE_MODE_SESSION_KEY)
    return override if override in (BREAKFAST_MODE, LUNCH_MODE) else automatic_capture_mode()


def capture_mode_context(request):
    mode = current_capture_mode(request)
    return {
        "capture_mode": mode,
        "capture_mode_label": "Modo desayunos" if mode == BREAKFAST_MODE else "Modo comida",
        "capture_mode_next": LUNCH_MODE if mode == BREAKFAST_MODE else BREAKFAST_MODE,
        "capture_mode_next_label": "Cambiar a comida" if mode == BREAKFAST_MODE else "Cambiar a desayunos",
    }


def auto_meal_slot(product, daily_menu):
    if product.pk in {daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id}:
        return "first"
    if product.pk in {daily_menu.second_course_one_id, daily_menu.second_course_two_id}:
        return "second"
    stew_ids = {
        product_id for product_id in (
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id,
        ) if product_id
    }
    if product.pk in stew_ids or (
        product.component_type == Product.ComponentType.GRILL
        and product.eligible_for_executive_meal
    ):
        return "main"
    return None


def planned_auto_meal_selection(request, account_id, slot, product_id, chicken_piece=""):
    all_builders = request.session.get(AUTO_MEAL_SESSION_KEY, {})
    builders = [dict(builder) for builder in all_builders.get(str(account_id), [])]
    if builders:
        builder = builders[0]
        if slot in builder:
            labels = {"first": "primer tiempo", "second": "segundo tiempo", "main": "tercer tiempo"}
            missing = [label for key, label in labels.items() if key not in builder]
            raise ValidationError(
                "Completa la comida actual antes de iniciar otra. Falta: " + ", ".join(missing) + "."
            )
    else:
        builder = {}
        builders.append(builder)
    builder[slot] = product_id
    if slot == "main" and chicken_piece:
        builder["chicken_piece"] = chicken_piece
    completed = dict(builder) if all(key in builder for key in ("first", "second", "main")) else None
    if completed:
        builders.remove(builder)
    return all_builders, builders, completed


def save_auto_meal_builders(request, account_id, all_builders, builders):
    if builders:
        all_builders[str(account_id)] = builders
    else:
        all_builders.pop(str(account_id), None)
    request.session[AUTO_MEAL_SESSION_KEY] = all_builders
    request.session.modified = True


def clear_auto_meal_builders(request, account_id):
    all_builders = request.session.get(AUTO_MEAL_SESSION_KEY, {})
    if all_builders.pop(str(account_id), None) is not None:
        request.session[AUTO_MEAL_SESSION_KEY] = all_builders
        request.session.modified = True


def waiter_queryset():
    return get_user_model().objects.filter(
        is_active=True, groups__name=WAITER,
    ).distinct().order_by("first_name", "username")


def ticket_summary(account):
    grouped = {}
    standard_quantities = {}
    candidate_quantities = {}
    total = Decimal("0")
    for item in account.items.select_related("product", "main_course_product", "daily_menu").all():
        key = (
            f"product-{item.product_id}-{item.chicken_piece}-{item.is_package_candidate}-{item.configuration_signature}"
            if item.product_id else f"item-{item.pk}"
        )
        if key not in grouped:
            if item.item_type == TableAccountItem.ItemType.PACKAGE:
                description_parts = [
                    item.first_course_snapshot or "Primer tiempo pendiente",
                    item.second_course_snapshot or "Segundo tiempo pendiente",
                    item.main_course_snapshot or "Tercer tiempo pendiente",
                ]
                if item.chicken_piece:
                    description_parts.append({"leg": "Pierna", "thigh": "Muslo"}.get(
                        item.chicken_piece, item.chicken_piece,
                    ))
                elif (
                    item.main_course_product
                    and item.main_course_product.component_type == Product.ComponentType.CHICKEN_STEW
                ):
                    description_parts.append("Pieza de pollo pendiente")
                if item.egg_name_snapshot:
                    description_parts.append(f"Con {item.egg_name_snapshot}")
                if item.bread:
                    description_parts.append("Con bolillo")
            else:
                description_parts = []
                if item.chicken_piece:
                    description_parts.append(
                        {"leg": "Pierna", "thigh": "Muslo"}.get(
                            item.chicken_piece, item.chicken_piece,
                        )
                    )
                if item.is_package_candidate:
                    description_parts.append("Esperando completar paquete")
                if item.is_customized:
                    description_parts.extend(item.configuration_snapshot.get("differences", []))
            grouped[key] = {
                "item_id": item.pk,
                "product_id": item.product_id,
                "name": (
                    f"{item.product_name_snapshot} ({item.customization_comment})"
                    if item.customization_comment else item.product_name_snapshot
                ),
                "description": " · ".join(description_parts),
                "quantity": 0,
                "subtotal": Decimal("0"),
                "is_package": item.item_type == TableAccountItem.ItemType.PACKAGE,
                "package_id": item.package_id,
                "is_complete": item.is_complete,
                "is_customized": item.is_customized,
                "first_course_id": item.first_course_product_id,
                "second_course_id": item.second_course_product_id,
                "main_course_id": item.main_course_product_id,
                "chicken_piece": item.chicken_piece,
                "with_water": item.with_water,
                "bread": item.bread,
                "egg_product_id": item.egg_product_id,
                "refill_extra": item.refill_extra,
                "edit_dialog_id": f"package-edit-{item.pk}",
            }
        grouped[key]["quantity"] += item.quantity
        grouped[key]["subtotal"] += item.subtotal
        total += item.subtotal
        if item.product_id and not item.is_package_candidate:
            product_key = str(item.product_id)
            standard_quantities[product_key] = standard_quantities.get(product_key, 0) + item.quantity
        if item.product_id and item.is_package_candidate:
            product_key = str(item.product_id)
            candidate_quantities[product_key] = candidate_quantities.get(product_key, 0) + item.quantity
    items = list(grouped.values())
    for item in items:
        item["subtotal_display"] = f"{item['subtotal']:.2f}"
        item["change_url"] = reverse(
            "tables:table_item_change",
            args=(account.pk, item["item_id"]),
        )
        if item["is_package"]:
            item["edit_url"] = reverse(
                "tables:table_package_edit",
                args=(account.pk, item["package_id"], item["item_id"]),
            )
    return {
        "items": items,
        "total": total,
        "total_display": f"{total:.2f}",
        "count": sum(item["quantity"] for item in items),
        "standard_quantities": standard_quantities,
        "candidate_quantities": candidate_quantities,
    }


def wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_map(request):
    tables = DiningTable.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "accounts",
            queryset=TableAccount.objects.filter(status=TableAccount.Status.OPEN).select_related(
                "assigned_waiter", "opened_by",
            ),
            to_attr="open_accounts",
        )
    )
    can_choose_waiter = user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    context = {
        "tables": tables,
        "waiters": waiter_queryset() if can_choose_waiter else (),
        "can_choose_waiter": can_choose_waiter,
    }
    context.update(capture_mode_context(request))
    return render(request, "tables/table_map.html", context)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_capture_mode_switch(request):
    requested_mode = request.POST.get("capture_mode")
    if requested_mode in (BREAKFAST_MODE, LUNCH_MODE):
        request.session[CAPTURE_MODE_SESSION_KEY] = requested_mode
    next_url = request.POST.get("next") or reverse("tables:table_map")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("tables:table_map")
    return redirect(next_url)


@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_account_history(request):
    today = timezone.localdate()
    period = request.GET.get("period", "today")
    customer_query = " ".join(request.GET.get("customer", "").split())[:100]
    table_query = " ".join(request.GET.get("table", "").split())[:60]
    if period == "week":
        start_date = today - timedelta(days=today.weekday())
    else:
        period = "today"
        start_date = today
    accounts = TableAccount.objects.filter(
        opened_at__date__range=(start_date, today),
    ).select_related("table", "assigned_waiter", "opened_by", "closed_by").annotate(
        consumption_count=Sum("items__quantity"),
        current_total=Sum("items__subtotal"),
    ).order_by("-opened_at")
    if user_has_any_role(request.user, (WAITER,)) and not user_has_any_role(request.user, (ADMIN, ORDER_TAKER)):
        accounts = accounts.filter(assigned_waiter=request.user)
    if customer_query:
        accounts = accounts.filter(customer_name__icontains=customer_query)
    if table_query:
        accounts = accounts.filter(table__name__icontains=table_query)
    account_list = list(accounts)
    closed_accounts = [account for account in account_list if account.status == TableAccount.Status.CLOSED]
    closed_total = sum(
        (account.total_paid or Decimal("0") for account in closed_accounts),
        start=Decimal("0"),
    )
    return render(request, "tables/table_account_history.html", {
        "accounts": account_list,
        "period": period,
        "start_date": start_date,
        "today": today,
        "closed_count": len(closed_accounts),
        "closed_total": closed_total,
        "customer_query": customer_query,
        "table_query": table_query,
    })


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_open(request, table_id):
    table = get_object_or_404(DiningTable, pk=table_id)
    if user_has_any_role(request.user, (ADMIN, ORDER_TAKER)):
        assigned_waiter = get_object_or_404(
            get_user_model(), pk=request.POST.get("assigned_waiter"),
        )
    else:
        assigned_waiter = request.user
    try:
        account = open_table_account(
            table=table, assigned_waiter=assigned_waiter, opened_by=request.user,
        )
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("tables:table_map")
    messages.success(request, f"La cuenta de {table.name} quedó abierta.")
    return redirect("tables:table_detail", account_id=account.pk)


@never_cache
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_detail(request, account_id):
    account = get_object_or_404(
        TableAccount.objects.select_related(
            "table", "assigned_waiter", "opened_by", "closed_by", "tip_recipient",
        ).prefetch_related("items__product", "activities__actor"),
        pk=account_id,
    )
    capture_mode = current_capture_mode(request)
    visibility_field = "show_on_table_breakfast" if capture_mode == BREAKFAST_MODE else "show_on_table_lunch"
    order_field = "table_breakfast_order" if capture_mode == BREAKFAST_MODE else "table_lunch_order"
    category_queryset = Category.objects.filter(**{visibility_field: True}).order_by(
        order_field, "name",
    ).prefetch_related(Prefetch(
        "products",
        queryset=Product.objects.filter(
            is_available=True, is_sold_individually=True,
        ).prefetch_related("service_periods"),
        to_attr="candidate_products",
    ))
    category_queryset = category_queryset.exclude(
        Q(name__iexact="Comida corrida")
        | Q(name__iexact="Comida ejecutiva")
        | Q(name__iexact="Comida por orden")
    )
    categories = []
    for category in category_queryset:
        category.available_products = [
            product for product in category.candidate_products
            if product_is_available_now(product, enforce_service_period=False)
        ]
        if category.available_products or category.show_table_packages:
            categories.append(category)
    daily_menu = DailyMenu.objects.filter(
        date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    ).select_related(
        "water_product", "chicken_consomme", "variable_first_course",
        "second_course_one", "second_course_two", "chicken_stew", "beef_stew",
        "varied_stew", "beans_order",
    ).first()
    from menu.catalog import limit_cold_drinks_to_daily_water

    categories = limit_cold_drinks_to_daily_water(
        categories, daily_menu, "available_products", keep_package_categories=True,
    )
    for category in categories:
        category.available_products = filter_products_by_stock(
            category.available_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.TABLE,
        )
    # NOTA TEMPORAL PARA APRENDIZAJE: Envases se consulta por su clasificación y no
    # por el nombre de la categoría; así puede cambiarse de categoría sin romper la
    # barra rápida. Los precios continúan perteneciendo al catálogo. Borra esta nota.
    packaging_products = list(Product.objects.filter(
        is_available=True,
        is_sold_individually=True,
    ).exclude(packaging_kind=Product.PackagingKind.NONE).order_by("sort_order", "name"))
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # "Comida por orden" usa una categoría como marcador de posición, pero su contenido
    # real sale del menú diario. Esta lista mezcla ese acceso virtual con las categorías
    # normales respetando el orden configurado para Mesas · Comida. Borra esta nota.
    lunch_category_navigation = []
    if capture_mode == LUNCH_MODE:
        order_category = Category.objects.filter(name__iexact="Comida por orden").first()
        order_position = order_category.table_lunch_order if order_category else None
        for category in categories:
            lunch_category_navigation.append({
                "kind": "category",
                "position": category.table_lunch_order,
                "name": category.name,
                "category": category,
            })
        lunch_category_navigation.append({
            "kind": "daily_orders",
            "position": order_position if order_position is not None else 10**9,
            "name": "Comida por orden",
            "category": None,
        })
        lunch_category_navigation.sort(key=lambda item: (item["position"], item["name"]))
    ticket = ticket_summary(account)
    daily_order_products = []
    running_meal_products = []
    executive_meal_products = []
    if capture_mode == LUNCH_MODE and daily_menu:
        first_and_second_ids = [product_id for product_id in (
            daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id,
            daily_menu.second_course_one_id, daily_menu.second_course_two_id,
        ) if product_id]
        stew_ids = [product_id for product_id in (
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id,
        ) if product_id]
        meal_component_ids = first_and_second_ids + stew_ids
        daily_order_ids = meal_component_ids + ([daily_menu.beans_order_id] if daily_menu.beans_order_id else [])
        smart_candidates = Product.objects.filter(
            pk__in=daily_order_ids,
            is_available=True,
        ).prefetch_related("service_periods")
        smart_candidates_by_id = {product.pk: product for product in smart_candidates}
        daily_order_products = [
            smart_candidates_by_id[product_id] for product_id in daily_order_ids
            if product_id in smart_candidates_by_id
            and product_is_available_now(
                smart_candidates_by_id[product_id], require_individual=False,
                enforce_service_period=False,
            )
        ]
        running_meal_products = [
            smart_candidates_by_id[product_id] for product_id in meal_component_ids
            if product_id in smart_candidates_by_id
            and product_is_available_now(
                smart_candidates_by_id[product_id], require_individual=False,
                enforce_service_period=False,
            )
        ]
        daily_order_products = filter_products_by_stock(
            daily_order_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.TABLE,
        )
        running_meal_products = filter_products_by_stock(
            running_meal_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.TABLE,
        )
        grill_candidates = Product.objects.filter(
            component_type=Product.ComponentType.GRILL,
            eligible_for_executive_meal=True,
            is_available=True,
        ).prefetch_related("service_periods").order_by("category__name", "name")
        executive_meal_products = [
            smart_candidates_by_id[product_id] for product_id in first_and_second_ids
            if product_id in smart_candidates_by_id
            and product_is_available_now(
                smart_candidates_by_id[product_id], require_individual=False,
                enforce_service_period=False,
            )
        ] + [
            product for product in grill_candidates
            if product_is_available_now(
                product, require_individual=False, enforce_service_period=False,
            )
        ]
        executive_meal_products = filter_products_by_stock(
            executive_meal_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.TABLE,
        )
    package_options = []
    if daily_menu:
        # NOTA TEMPORAL PARA APRENDIZAJE: igual que Pedidos, Mesas conserva el
        # formulario Django para validar pero entrega también los productos completos
        # para poder dibujar sus fotografías. Borra esta nota después de leerla.
        for package in MealPackage.objects.filter(is_active=True):
            package_form = TablePackageForm(
                package=package, daily_menu=daily_menu, prefix=f"package-{package.pk}",
            )
            package_options.append({
                "package": package,
                "form": package_form,
                "first_products": filter_products_by_stock(list(package_form.fields["first_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.TABLE),
                "second_products": filter_products_by_stock(list(package_form.fields["second_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.TABLE),
                "main_products": filter_products_by_stock(list(package_form.fields["main_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.TABLE),
            })
    package_edit_options = []
    package_items = account.items.filter(
        item_type=TableAccountItem.ItemType.PACKAGE,
    ).select_related("package", "daily_menu")
    for item in package_items:
        source_menu = item.daily_menu
        if not source_menu:
            source_menu = DailyMenu.objects.filter(
                date=timezone.localdate(item.added_at),
            ).first()
        if not source_menu or not item.package:
            continue
        initial = {
            "first_course": item.first_course_product_id,
            "second_course": item.second_course_product_id,
            "main_course": item.main_course_product_id,
            "chicken_piece": item.chicken_piece,
            "with_water": item.with_water,
            "bread": item.bread,
            "egg_product": item.egg_product_id,
            "refill_extra": item.refill_extra,
            "customization_comment": item.customization_comment,
        }
        prefix = f"package-edit-{item.pk}"
        package_edit_options.append({
            "item": item,
            "package": item.package,
            "daily_menu": source_menu,
            "prefix": prefix,
            "form": TablePackageForm(
                package=item.package, daily_menu=source_menu, initial=initial, prefix=prefix,
            ),
        })
    can_reassign = user_has_any_role(request.user, (ADMIN, WAITER))
    selector_products = {
        product.pk: product for category in categories for product in category.available_products
    }
    selector_products.update({product.pk: product for product in packaging_products})
    selector_products.update({product.pk: product for product in daily_order_products})
    selector_products.update({product.pk: product for product in running_meal_products})
    selector_products.update({product.pk: product for product in executive_meal_products})
    selector_product_records = Product.objects.filter(
        pk__in=selector_products,
    ).prefetch_related("option_groups__options")
    product_customizations = {
        str(product.pk): serialize_product_selector(product) for product in selector_product_records
    }
    customizable_ids = {int(product_id) for product_id in product_customizations}
    daily_order_ids = {product.pk for product in daily_order_products}
    for category in categories:
        for product in category.available_products:
            product.has_customization = product.pk in customizable_ids
    for product in daily_order_products:
        product.has_customization = product.pk in customizable_ids
    catalog_search_products = sorted(selector_products.values(), key=lambda product: product.name.casefold())
    for product in catalog_search_products:
        product.has_customization = product.pk in customizable_ids
        product.is_daily_order_search = product.pk in daily_order_ids
    context = {
        "account": account,
        "categories": categories,
        "packaging_products": packaging_products,
        "lunch_category_navigation": lunch_category_navigation,
        "ticket": ticket,
        "daily_menu": daily_menu,
        "package_options": package_options,
        "egg_options": [{"id": egg.pk, "name": egg.name, "price": str(egg.price)} for egg in egg_products()],
        "egg_initials": {str(option["item"].pk): option["item"].egg_product_id for option in package_edit_options},
        "package_edit_options": package_edit_options,
        "daily_order_products": daily_order_products,
        "running_meal_products": running_meal_products,
        "executive_meal_products": executive_meal_products,
        "product_customizations": product_customizations,
        "catalog_search_products": catalog_search_products,
        "can_reassign": can_reassign,
        "waiters": waiter_queryset() if can_reassign else (),
        "close_form": TableAccountCloseForm(account_total=ticket["total"]),
    }
    context.update(capture_mode_context(request))
    return render(request, "tables/table_detail.html", context)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_item_add(request, account_id, product_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    product = get_object_or_404(Product.objects.prefetch_related("service_periods"), pk=product_id)
    try:
        raw_option_ids = (
            request.POST.getlist("option_ids")
            if request.POST.get("customization_selected") == "1" else None
        )
        add_product_to_table(
            account=account, product=product, added_by=request.user,
            raw_option_ids=raw_option_ids,
            customization_comment=(
                request.POST.get("customization_comment", "")
                if request.POST.get("customization_selected") == "1" else ""
            ),
        )
    except ValidationError as error:
        if wants_json(request):
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
    else:
        if wants_json(request):
            return JsonResponse({"ok": True, "ticket": ticket_summary(account)})
    return redirect("tables:table_detail", account_id=account.pk)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_daily_order_add(request, account_id, product_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    product = get_object_or_404(Product.objects.prefetch_related("service_periods"), pk=product_id)
    daily_menu = get_object_or_404(
        DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    try:
        add_daily_menu_product_to_table(
            account=account, product=product, daily_menu=daily_menu, added_by=request.user,
            chicken_piece=request.POST.get("chicken_piece", ""),
            raw_option_ids=(
                request.POST.getlist("option_ids")
                if request.POST.get("customization_selected") == "1" else None
            ),
            customization_comment=(
                request.POST.get("customization_comment", "")
                if request.POST.get("customization_selected") == "1" else ""
            ),
        )
    except ValidationError as error:
        if wants_json(request):
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
    else:
        if wants_json(request):
            return JsonResponse({"ok": True, "ticket": ticket_summary(account)})
    return redirect("tables:table_detail", account_id=account.pk)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_auto_meal_add(request, account_id, product_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    product = get_object_or_404(Product.objects.prefetch_related("service_periods"), pk=product_id)
    daily_menu = get_object_or_404(
        DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    slot = auto_meal_slot(product, daily_menu)
    if not slot:
        return JsonResponse({
            "ok": False,
            "error": "Este producto no puede formar un paquete del menú de hoy.",
        }, status=400)
    requested_chicken_piece = request.POST.get("chicken_piece", "")
    try:
        all_builders, builders, completed = planned_auto_meal_selection(
            request, account.pk, slot, product.pk, requested_chicken_piece,
        )
        package_item = add_auto_meal_component(
            account=account, product=product, daily_menu=daily_menu,
            completed_selection=completed, added_by=request.user,
            chicken_piece=(completed or {}).get("chicken_piece", requested_chicken_piece),
            raw_option_ids=(request.POST.getlist("option_ids") if request.POST.get("customization_selected") == "1" else None),
            customization_comment=(request.POST.get("customization_comment", "") if request.POST.get("customization_selected") == "1" else ""),
            egg_product=selected_egg(request.POST.get("egg_product")),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    save_auto_meal_builders(request, account.pk, all_builders, builders)
    return JsonResponse({
        "ok": True,
        "ticket": ticket_summary(account),
        "auto_package_created": package_item is not None,
    })


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_item_change(request, account_id, item_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    item = get_object_or_404(TableAccountItem, pk=item_id, account=account)
    try:
        change_item_in_ticket(
            account=account, item=item, action=request.POST.get("action"), changed_by=request.user,
        )
    except ValidationError as error:
        if wants_json(request):
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
    else:
        clear_auto_meal_builders(request, account.pk)
        if wants_json(request):
            return JsonResponse({"ok": True, "ticket": ticket_summary(account)})
    return redirect("tables:table_detail", account_id=account.pk)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_standard_product_decrease(request, account_id, product_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    product = get_object_or_404(
        Product.objects.prefetch_related("option_groups__options"), pk=product_id,
    )
    standard_signature = resolve_product_selection(product)["signature"]
    item = account.items.filter(
        product=product, is_package_candidate=False, is_customized=False,
        configuration_signature=standard_signature,
    ).order_by("-id").first()
    if item:
        try:
            change_item_in_ticket(account=account, item=item, action="decrease", changed_by=request.user)
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, "ticket": ticket_summary(account)})


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_auto_meal_decrease(request, account_id, product_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    product = get_object_or_404(Product.objects.prefetch_related("option_groups__options"), pk=product_id)
    item = account.items.filter(
        product=product, is_package_candidate=True, is_customized=False,
        configuration_signature=resolve_product_selection(product)["signature"],
    ).order_by("-id").first()
    if item:
        try:
            change_item_in_ticket(account=account, item=item, action="decrease", changed_by=request.user)
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        clear_auto_meal_builders(request, account.pk)
    return JsonResponse({"ok": True, "ticket": ticket_summary(account)})


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_package_add(request, account_id, package_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    package = get_object_or_404(MealPackage, pk=package_id, is_active=True)
    daily_menu = get_object_or_404(
        DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    form = TablePackageForm(
        request.POST, package=package, daily_menu=daily_menu, prefix=f"package-{package.pk}",
    )
    if not form.is_valid():
        error_messages = [
            error["message"]
            for field_errors in form.errors.get_json_data().values()
            for error in field_errors
        ]
        return JsonResponse({
            "ok": False,
            "error": " ".join(error_messages) or "Revisa todas las opciones del paquete.",
        }, status=400)
    try:
        form.cleaned_data["is_complete"] = form.is_complete()
        add_package_to_table(
            account=account, package=package, daily_menu=daily_menu,
            cleaned_data=form.cleaned_data, added_by=request.user,
            packaging_quantities=parse_packaging_quantities(request.POST),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, "ticket": ticket_summary(account)})


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_package_edit(request, account_id, package_id, item_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    item = get_object_or_404(
        TableAccountItem.objects.select_related("daily_menu", "package"), pk=item_id, account=account,
        item_type=TableAccountItem.ItemType.PACKAGE, package_id=package_id,
    )
    package = get_object_or_404(MealPackage, pk=package_id)
    daily_menu = item.daily_menu or DailyMenu.objects.filter(
        date=timezone.localdate(item.added_at),
    ).first()
    if not daily_menu:
        return JsonResponse({
            "ok": False,
            "error": "No encontramos el menú original de esta comida. Conserva la cuenta abierta y solicita revisión.",
        }, status=400)
    prefix = request.POST.get("form_prefix") or f"package-{package.pk}"
    form = TablePackageForm(
        request.POST, package=package, daily_menu=daily_menu, prefix=prefix,
    )
    if not form.is_valid():
        error_messages = [
            error["message"]
            for field_errors in form.errors.get_json_data().values()
            for error in field_errors
        ]
        return JsonResponse({
            "ok": False,
            "error": " ".join(error_messages) or "Revisa las opciones del paquete.",
        }, status=400)
    form.cleaned_data["is_complete"] = form.is_complete()
    try:
        update_table_package(
            account=account, item=item, package=package, daily_menu=daily_menu,
            cleaned_data=form.cleaned_data, changed_by=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, "ticket": ticket_summary(account)})


@require_POST
@role_required(ADMIN, WAITER)
def table_reassign(request, account_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    assigned_waiter = get_object_or_404(
        get_user_model(), pk=request.POST.get("assigned_waiter"),
    )
    try:
        account = reassign_table_account(account=account, assigned_waiter=assigned_waiter, changed_by=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"{account.table.name} cambió de mesero responsable.")
    return redirect("tables:table_detail", account_id=account.pk)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_customer_name_update(request, account_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    if account.status != TableAccount.Status.OPEN:
        if wants_json(request):
            return JsonResponse({"ok": False, "error": "El nombre solamente puede modificarse mientras la cuenta está abierta."}, status=400)
        messages.error(request, "El nombre solamente puede modificarse mientras la cuenta está abierta.")
        return redirect("tables:table_detail", account_id=account.pk)
    customer_name = " ".join(request.POST.get("customer_name", "").split())
    if len(customer_name) > 100:
        if wants_json(request):
            return JsonResponse({"ok": False, "error": "El nombre del cliente no puede superar 100 caracteres."}, status=400)
        messages.error(request, "El nombre del cliente no puede superar 100 caracteres.")
    else:
        previous_name = account.customer_name
        if customer_name != previous_name:
            account.customer_name = customer_name
            account.save(update_fields=("customer_name",))
            record_activity(account=account, actor=request.user, action=TableActivity.Action.CUSTOMER, description=f"{previous_name or 'Sin nombre'} → {customer_name or 'Sin nombre'}")
        if wants_json(request):
            return JsonResponse({"ok": True, "customer_name": customer_name})
        messages.success(request, "El nombre del cliente fue actualizado." if customer_name else "La cuenta quedó sin nombre de cliente.")
    return redirect("tables:table_detail", account_id=account.pk)


@require_POST
@role_required(*SECTION_ROLE_MATRIX["tables"])
def table_close(request, account_id):
    account = get_object_or_404(TableAccount, pk=account_id)
    current_total = ticket_summary(account)["total"]
    form = TableAccountCloseForm(request.POST, account_total=current_total)
    if not form.is_valid():
        error_messages = [
            error["message"]
            for field_errors in form.errors.get_json_data().values()
            for error in field_errors
        ]
        messages.error(request, " ".join(error_messages) or "Revisa los datos del cobro.")
        return redirect("tables:table_detail", account_id=account.pk)
    try:
        account = close_table_account(
            account=account, cleaned_data=form.cleaned_data, closed_by=request.user,
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(
            request,
            f"La cuenta de {account.table.name} quedó cerrada y la mesa está disponible.",
        )
    return redirect("tables:table_detail", account_id=account.pk)


@role_required(ADMIN, WAITER, ORDER_TAKER)
def table_kitchen_print(request, account_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta ruta abre la comanda completa; la selección
    # parcial vive en la variante "modificado". Borra esta nota al leerla.
    account = get_object_or_404(
        TableAccount.objects.select_related("table", "assigned_waiter", "opened_by"),
        pk=account_id,
    )
    context = table_print_context(account)
    context.update({
        "items": [printable_item(item) for item in account.items.all()],
        "back_url": reverse("tables:table_detail", args=(account.pk,)),
    })
    return render(request, "printing/kitchen_ticket.html", context)


@role_required(ADMIN, WAITER, ORDER_TAKER)
def table_kitchen_custom_print(request, account_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta variante permite escoger partidas sin
    # alterar las cantidades reales del ticket. Borra esta nota al leerla.
    account = get_object_or_404(
        TableAccount.objects.select_related("table", "assigned_waiter", "opened_by"),
        pk=account_id,
    )
    queryset = account.items.select_related("product", "package").all()
    selected, result = selected_printable_items(request, queryset)
    context = table_print_context(account)
    context["back_url"] = reverse("tables:table_detail", args=(account.pk,))
    if request.method == "POST" and selected is not None and not result:
        try:
            job = queue_ticket(source_type="table", source=account, ticket_type="kitchen", items=selected, user=request.user)
        except ValueError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, f"Comanda enviada a la Dell (trabajo #{job.pk}).")
        return redirect("tables:table_detail", account_id=account.pk)
    context.update({
        "selection_items": [printable_item(item) for item in queryset],
        "selection_errors": result if request.method == "POST" else [],
        "submit_url": reverse("tables:table_kitchen_custom_print", args=(account.pk,)),
    })
    return render(request, "printing/kitchen_select.html", context)


@role_required(ADMIN, WAITER, ORDER_TAKER)
def table_payment_print(request, account_id):
    account = get_object_or_404(
        TableAccount.objects.select_related("table", "assigned_waiter", "opened_by"),
        pk=account_id,
    )
    context = table_print_context(account)
    context.update({
        "items": [printable_item(item) for item in account.items.all()],
        "back_url": reverse("tables:table_detail", args=(account.pk,)),
    })
    return render(request, "printing/payment_ticket.html", context)
