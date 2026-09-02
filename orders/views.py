# NOTA TEMPORAL PARA APRENDIZAJE:
# Las vistas finales forman el panel operativo y las acciones seguras de reparto.
# El flujo público exige modalidad en sesión antes del menú; checkout usa esa decisión
# para mostrar solo los datos necesarios. Borra esta nota después de leerla.
# Corrida y ejecutiva permiten pedidos anticipados antes de la 1 p. m. con un aviso.
# Productos generales también respetan la visibilidad pública de su categoría según horario.

from datetime import time

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, SECTION_ROLE_MATRIX, role_required, user_has_any_role
from menu.models import Category, DailyMenu, MealPackage, Product
from menu.selection import resolve_product_selection, serialize_product_selector

from .cart import add_package, add_product, cart_control_summary, clear, decrease_product, get_order_mode, product_is_orderable, remove_item, resolve_cart, set_order_mode, update_item
from .forms import CustomerAddressForm, CustomerForm, DeliveryTipForm, InternalOrderAutosaveForm, InternalOrderForm, InternalPackageExtrasForm, InternalPackageForm, PackageCartForm, ProductCartForm, PublicCheckoutForm, PublicOrderModeForm
from .models import Customer, CustomerAddress, Order, OrderItem
from .services import ACTION_LABELS, add_internal_auto_meal_component, add_internal_order_package, add_internal_order_product, add_water_to_internal_package, assign_delivery, autosave_internal_order_customer, available_order_actions, change_internal_order_item, close_internal_order_capture, confirm_cash_handoff, create_public_cart_order, save_internal_order, start_internal_order, transition_order, update_cashier_payment, update_delivery_tip, update_internal_order_item_note, update_internal_order_note, update_internal_package_extras


INTERNAL_MENU_MODE_KEY = "internal_order_menu_mode"
INTERNAL_AUTO_MEAL_SESSION_KEY = "internal_order_auto_meal_builders"


def internal_auto_meal_slot(product, daily_menu):
    if product.pk in {daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id}:
        return "first"
    if product.pk in {daily_menu.second_course_one_id, daily_menu.second_course_two_id}:
        return "second"
    if product.pk in {daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id} or (
        product.component_type == Product.ComponentType.GRILL and product.eligible_for_executive_meal
    ):
        return "main"
    return None


def plan_internal_auto_meal(request, order_id, slot, product_id, chicken_piece=""):
    all_builders = request.session.get(INTERNAL_AUTO_MEAL_SESSION_KEY, {})
    builders = [dict(builder) for builder in all_builders.get(str(order_id), [])]
    builder = next((candidate for candidate in builders if slot not in candidate), None)
    if builder is None:
        builder = {}
        builders.append(builder)
    builder[slot] = product_id
    if slot == "main" and chicken_piece:
        builder["chicken_piece"] = chicken_piece
    completed = dict(builder) if all(key in builder for key in ("first", "second", "main")) else None
    if completed:
        builders.remove(builder)
    return all_builders, builders, completed


def save_internal_auto_meals(request, order_id, all_builders, builders):
    if builders:
        all_builders[str(order_id)] = builders
    else:
        all_builders.pop(str(order_id), None)
    request.session[INTERNAL_AUTO_MEAL_SESSION_KEY] = all_builders
    request.session.modified = True


def clear_internal_auto_meals(request, order_id):
    all_builders = request.session.get(INTERNAL_AUTO_MEAL_SESSION_KEY, {})
    if all_builders.pop(str(order_id), None) is not None:
        request.session[INTERNAL_AUTO_MEAL_SESSION_KEY] = all_builders
        request.session.modified = True


def internal_order_ticket(order):
    items = []
    quantities = {}
    candidate_quantities = {}
    for item in order.items.all():
        base_name = item.product_name_snapshot or item.package_name_snapshot
        if item.item_type == OrderItem.ItemType.PACKAGE and item.with_water:
            base_name = f"{base_name} con agua"
        description_parts = []
        if item.item_type == OrderItem.ItemType.PACKAGE:
            description_parts = [
                item.first_course_name_snapshot, item.second_course_name_snapshot,
                item.main_course_name_snapshot,
            ]
            if item.tortillas:
                description_parts.append("Con tortillas")
            if item.beans:
                description_parts.append("Con frijoles")
        items.append({
            "id": item.pk,
            "name": f"{base_name} ({item.customization_comment})" if item.customization_comment else base_name,
            "quantity": item.quantity, "subtotal": f"{item.subtotal:.2f}",
            "is_customized": item.is_customized,
            "is_package_candidate": item.is_package_candidate,
            "description": "" if item.is_package_candidate else " · ".join(filter(None, description_parts)),
            "is_package": item.item_type == OrderItem.ItemType.PACKAGE,
            "with_water": item.with_water, "tortillas": item.tortillas,
            "beans": item.beans, "comment": item.customization_comment,
            "edit_extras_url": reverse("orders:internal_order_package_extras", args=(order.pk, item.pk)) if item.item_type == OrderItem.ItemType.PACKAGE else "",
            "edit_note_url": reverse("orders:internal_order_item_note", args=(order.pk, item.pk)),
            "change_url": reverse("orders:internal_order_item_change", args=(order.pk, item.pk)),
        })
        if item.item_type == OrderItem.ItemType.PRODUCT and not item.is_customized:
            target = candidate_quantities if item.is_package_candidate else quantities
            target[str(item.product_id)] = target.get(str(item.product_id), 0) + item.quantity
    return {
        "items": items, "total": f"{order.total:.2f}",
        "count": sum(item["quantity"] for item in items), "quantities": quantities,
        "candidate_quantities": candidate_quantities, "note": order.notes,
    }


def public_order_mode(request):
    form = PublicOrderModeForm(request.POST or None, initial={"order_type": get_order_mode(request.session)})
    if request.method == "POST" and form.is_valid():
        set_order_mode(request.session, form.cleaned_data["order_type"])
        return redirect("public_portal:menu")
    return render(request, "orders/public_order_mode.html", {"form": form})


def public_package_order(request, package_type):
    if not get_order_mode(request.session):
        return redirect("public_portal:order_mode")
    package = get_object_or_404(MealPackage, package_type=package_type, is_active=True)
    daily_menu = get_object_or_404(
        DailyMenu.objects.select_related(
            "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew",
            "beef_stew", "varied_stew",
        ),
        date=timezone.localdate(),
        status=DailyMenu.Status.PUBLISHED,
    )
    form = PackageCartForm(request.POST or None, package=package, daily_menu=daily_menu)
    if request.method == "POST" and form.is_valid():
        add_package(request.session, package=package, daily_menu=daily_menu, cleaned_data=form.cleaned_data)
        messages.success(request, "La comida fue agregada al carrito.")
        return redirect("public_portal:cart")
    return render(request, "orders/public_package_order.html", {
        "package": package, "daily_menu": daily_menu, "form": form,
        "advance_food_order": timezone.localtime().time() < time(13, 0),
    })


@require_POST
def public_product_add(request, product_id):
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not get_order_mode(request.session):
        if wants_json:
            return JsonResponse({"ok": False, "error": "Primero selecciona la modalidad del pedido."}, status=400)
        return redirect("public_portal:order_mode")
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "service_periods", "option_groups__options",
        ),
        pk=product_id,
    )
    form = ProductCartForm(request.POST)
    daily_component_types = {
        Product.ComponentType.CHICKEN_CONSOMME,
        Product.ComponentType.VARIABLE_FIRST_COURSE,
        Product.ComponentType.SECOND_COURSE,
        Product.ComponentType.CHICKEN_STEW,
        Product.ComponentType.BEEF_STEW,
        Product.ComponentType.VARIED_STEW,
    }
    visibility_field = (
        "show_on_public_breakfast"
        if timezone.localtime().time() < time(12, 30)
        else "show_on_public_lunch"
    )
    category_is_visible = (
        product.component_type in daily_component_types
        or getattr(product.category, visibility_field)
    )
    if not category_is_visible:
        error_message = "Ese producto no está visible en el menú de este horario."
    elif not product_is_orderable(product):
        error_message = "Ese producto no está disponible para pedir ahora."
    elif form.is_valid():
        try:
            raw_option_ids = (
                request.POST.getlist("option_ids")
                if request.POST.get("customization_selected") == "1" else None
            )
            raw_comment = (
                request.POST.get("customization_comment", "")
                if request.POST.get("customization_selected") == "1" else ""
            )
            selection = resolve_product_selection(product, raw_option_ids, raw_comment)
        except ValidationError as error:
            error_message = error.message
        else:
            add_product(
                request.session, product=product, quantity=form.cleaned_data["quantity"],
                selection=selection,
            )
            if wants_json:
                return JsonResponse({"ok": True, "cart": cart_control_summary(request.session)})
            messages.success(request, f"{product.name} fue agregado al carrito.")
            return redirect("public_portal:cart")
    else:
        error_message = "La cantidad solicitada no es válida."
    if wants_json:
        return JsonResponse({"ok": False, "error": error_message}, status=400)
    messages.error(request, error_message)
    return redirect("public_portal:menu")


@require_POST
def public_product_decrease(request, product_id):
    if not get_order_mode(request.session):
        return JsonResponse({"ok": False, "error": "Primero selecciona la modalidad del pedido."}, status=400)
    product = get_object_or_404(
        Product.objects.prefetch_related("option_groups__options"), pk=product_id,
    )
    standard = resolve_product_selection(product)
    decrease_product(
        request.session, product=product, configuration_signature=standard["signature"],
    )
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "cart": cart_control_summary(request.session)})
    return redirect("public_portal:menu")


def public_cart(request):
    order_type = get_order_mode(request.session)
    if not order_type:
        return redirect("public_portal:order_mode")
    return render(request, "orders/public_cart.html", {
        "cart": resolve_cart(request.session), "order_type": order_type,
        "order_type_label": dict(Order.OrderType.choices)[order_type],
    })


@require_POST
def public_cart_update(request, key):
    form = ProductCartForm(request.POST)
    if form.is_valid() and update_item(request.session, key=key, quantity=form.cleaned_data["quantity"]):
        messages.success(request, "La cantidad fue actualizada.")
    else:
        messages.error(request, "No fue posible actualizar esa partida.")
    return redirect("public_portal:cart")


@require_POST
def public_cart_remove(request, key):
    if remove_item(request.session, key=key):
        messages.success(request, "La partida fue eliminada.")
    return redirect("public_portal:cart")


def public_checkout(request):
    order_type = get_order_mode(request.session)
    if not order_type:
        return redirect("public_portal:order_mode")
    cart_data = resolve_cart(request.session)
    if not cart_data["items"]:
        messages.error(request, "Agrega al menos un producto antes de finalizar.")
        return redirect("public_portal:cart")
    form = PublicCheckoutForm(
        request.POST or None, cart_total=cart_data["total"], order_type=order_type
    )
    if request.method == "POST" and form.is_valid():
        if cart_data["invalid_count"]:
            form.add_error(None, "Hay partidas que dejaron de estar disponibles. Retíralas antes de continuar.")
        else:
            try:
                order = create_public_cart_order(cart_data=cart_data, cleaned_data=form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, str(error))
            else:
                clear(request.session)
                return redirect("public_portal:order_confirmation", public_token=order.public_token)
    return render(request, "orders/public_checkout.html", {
        "cart": cart_data, "form": form, "order_type": order_type,
    })


def public_order_confirmation(request, public_token):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), public_token=public_token,
        source=Order.Source.PUBLIC_WEB,
    )
    return render(request, "orders/public_order_confirmation.html", {"order": order})


def _folio_search_query(search):
    """Build a query for a short sequence or the visible DDMMNNN folio."""
    # NOTA TEMPORAL PARA APRENDIZAJE: aceptamos tanto el consecutivo corto (`1`)
    # como el folio completo (`0109001`). En el completo separamos DD, MM y el
    # consecutivo para consultar las columnas reales. Borra esta nota al leerla.
    digits = search.lstrip("#")
    if not digits.isdigit():
        return Q()
    query = Q(daily_number=int(digits))
    if len(digits) >= 5:
        query |= Q(
            operating_date__day=int(digits[:2]),
            operating_date__month=int(digits[2:4]),
            daily_number=int(digits[4:]),
        )
    return query


@role_required(*SECTION_ROLE_MATRIX["orders"])
def order_list(request):
    orders = Order.objects.prefetch_related("items")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    order_type = request.GET.get("order_type", "").strip()
    if search:
        number_query = _folio_search_query(search)
        orders = orders.filter(
            number_query | Q(customer_name__icontains=search) | Q(phone__icontains=search)
        )
    if status in Order.Status.values:
        orders = orders.filter(status=status)
    if order_type in Order.OrderType.values:
        orders = orders.filter(order_type=order_type)
    orders = list(orders)
    # NOTA TEMPORAL PARA APRENDIZAJE: preparamos textos cortos para que la plantilla
    # sea sólo presentación. La acción rápida omite Cancelar para evitar un clic
    # destructivo accidental desde el tablero. Borra esta nota después de leerla.
    for order in orders:
        items = list(order.items.all())
        names = []
        for item in items[:3]:
            name = item.product_name_snapshot if item.item_type == OrderItem.ItemType.PRODUCT else item.package_name_snapshot
            names.append(f"{item.quantity} × {name}")
        if len(items) > 3:
            names.append(f"+{len(items) - 3} más")
        order.ticket_summary = " · ".join(names) if names else "Sin productos"
        actions = [action for action in available_order_actions(order) if action != "cancel"]
        order.quick_action = actions[0] if actions else ""
        order.quick_action_label = ACTION_LABELS.get(order.quick_action, "")
    return render(request, "orders/order_list.html", {
        "orders": orders,
        "status_choices": Order.Status.choices,
        "order_type_choices": Order.OrderType.choices,
        "search": search,
        "selected_status": status,
        "selected_order_type": order_type,
        "can_capture_internal": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
    })


def _internal_order_initial(order):
    cash_bill = str(int(order.cash_tendered)) if order.cash_tendered in (20, 50, 100, 200, 500) else ""
    opened_at = timezone.localtime(order.created_at)
    return {
        "order_type": order.order_type,
        "agenda_customer_id": order.agenda_customer_id,
        "agenda_address_id": order.agenda_address_id,
        "customer_name": order.customer_name or ("Mostrador" if order.order_type == Order.OrderType.PICKUP else ""),
        "phone": order.phone,
        "requested_date": order.requested_date or opened_at.date(),
        "requested_time": order.requested_time or opened_at.time().replace(second=0, microsecond=0),
        "street": order.street, "exterior_number": order.exterior_number,
        "interior_number": order.interior_number,
        "neighborhood": order.neighborhood or ("del valle centro" if order.order_type == Order.OrderType.DELIVERY else ""),
        "references": order.references, "notes": order.notes,
        "payment_method": order.payment_method, "cash_bill": cash_bill,
        "cash_custom_amount": "" if cash_bill or not order.cash_tendered else order.cash_tendered,
        "pays_exact": order.payment_method == Order.PaymentMethod.CASH and not order.needs_change,
    }


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_create(request):
    try:
        order = start_internal_order(order_type=request.POST.get("order_type"), actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("orders:order_list")
    return redirect("orders:internal_order_edit", order_id=order.pk)


@role_required(ADMIN, ORDER_TAKER)
def customer_list(request):
    query = request.GET.get("q", "").strip()
    phone_query = "".join(character for character in query if character.isdigit())
    customers = Customer.objects.prefetch_related("addresses")
    if query:
        phone_filter = Q(phone_key__icontains=phone_query) if phone_query else Q(pk__isnull=True)
        customers = customers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
            | phone_filter
            | Q(addresses__street__icontains=query)
            | Q(addresses__neighborhood__icontains=query)
        ).distinct()
    return render(request, "orders/customer_list.html", {"customers": customers, "query": query})


@role_required(ADMIN, ORDER_TAKER)
def customer_create(request):
    form = CustomerForm(request.POST or None)
    address_form = CustomerAddressForm(request.POST or None, prefix="new")
    # NOTA TEMPORAL PARA APRENDIZAJE: el domicilio completo es opcional, pero si
    # se empieza a capturar exigimos calle y número exterior para no almacenar una
    # dirección inutilizable. Cliente y domicilio se guardan juntos. Borra esta nota.
    address_has_data = request.method == "POST" and any(
        request.POST.get(address_form.add_prefix(field), "").strip()
        for field in address_form.fields
    )
    forms_are_valid = (
        request.method == "POST" and form.is_valid()
        and (not address_has_data or address_form.is_valid())
    )
    if forms_are_valid:
        with transaction.atomic():
            customer = form.save()
            if address_has_data:
                address = address_form.save(commit=False)
                address.customer = customer
                address.save()
        messages.success(request, "El cliente y sus datos iniciales fueron agregados a la agenda.")
        return redirect("orders:customer_edit", customer_id=customer.pk)
    return render(request, "orders/customer_form.html", {
        "customer": None, "form": form, "address_forms": (),
        "new_address_form": address_form,
    })


@role_required(ADMIN, ORDER_TAKER)
def customer_edit(request, customer_id):
    customer = get_object_or_404(Customer.objects.prefetch_related("addresses"), pk=customer_id)
    form = CustomerForm(instance=customer)
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "customer":
            form = CustomerForm(request.POST, instance=customer)
            if form.is_valid():
                form.save()
                messages.success(request, "Los datos del cliente fueron actualizados.")
                return redirect("orders:customer_edit", customer_id=customer.pk)
        elif action == "new_address":
            address_form = CustomerAddressForm(request.POST, prefix="new")
            if address_form.is_valid():
                address = address_form.save(commit=False)
                address.customer = customer
                address.save()
                messages.success(request, "La dirección fue agregada.")
                return redirect("orders:customer_edit", customer_id=customer.pk)
        elif action.startswith("address_") and action.removeprefix("address_").isdigit():
            address = get_object_or_404(CustomerAddress, pk=int(action.removeprefix("address_")), customer=customer)
            address_form = CustomerAddressForm(request.POST, instance=address, prefix=f"address-{address.pk}")
            if address_form.is_valid():
                address_form.save()
                messages.success(request, "La dirección fue actualizada.")
                return redirect("orders:customer_edit", customer_id=customer.pk)
    address_forms = [(address, CustomerAddressForm(instance=address, prefix=f"address-{address.pk}")) for address in customer.addresses.all()]
    return render(request, "orders/customer_form.html", {
        "customer": customer, "form": form, "address_forms": address_forms,
        "new_address_form": CustomerAddressForm(prefix="new"),
    })


@role_required(ADMIN, ORDER_TAKER)
def customer_lookup(request):
    query = request.GET.get("q", "").strip()
    phone_query = "".join(character for character in query if character.isdigit())
    customers = Customer.objects.prefetch_related("addresses")
    if query:
        phone_filter = Q(phone_key__icontains=phone_query) if phone_query else Q(pk__isnull=True)
        customers = customers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
            | phone_filter
            | Q(addresses__street__icontains=query)
        ).distinct()[:10]
    else:
        customers = customers.none()
    return JsonResponse({"customers": [{
        "id": customer.pk, "name": customer.name, "phone": customer.phone,
        "notes": customer.notes,
        "edit_url": reverse("orders:customer_edit", args=(customer.pk,)),
        "addresses": [{
            "id": address.pk, "street": address.street,
            "exterior_number": address.exterior_number,
            "interior_number": address.interior_number,
            "neighborhood": address.neighborhood,
            "references": address.references,
        } for address in customer.addresses.all()],
    } for customer in customers]})


@role_required(ADMIN, ORDER_TAKER)
def internal_order_edit(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=order_id)
    close_failed = False
    form = InternalOrderForm(
        request.POST or None,
        initial=_internal_order_initial(order), order_total=order.total,
        closing=request.method == "POST" and request.POST.get("action") == "close",
    )
    if request.method == "POST" and form.is_valid():
        order = save_internal_order(form_data=form.cleaned_data, actor=request.user, order=order)
        if request.POST.get("action") == "close":
            try:
                close_internal_order_capture(order=order, actor=request.user)
            except ValidationError as error:
                close_failed = True
                form.add_error(None, error.message)
                messages.error(request, f"No se pudo cerrar el pedido: {error.message}")
            else:
                messages.success(request, f"{order.formatted_number} quedó confirmado y continúa disponible para modificaciones.")
                return redirect("orders:order_list")
        if not close_failed:
            messages.success(request, f"Datos de {order.formatted_number} actualizados.")
            # NOTA TEMPORAL PARA APRENDIZAJE: el pedido sigue como borrador, pero
            # regresamos al listado para que el telefonista pueda atender otro.
            # Borra esta nota después de leerla.
            return redirect("orders:order_list")
    if request.method == "POST" and not form.is_valid():
        messages.error(request, "No se guardaron los datos. Revisa los campos marcados debajo.")
    mode = request.session.get(INTERNAL_MENU_MODE_KEY)
    if mode not in {"breakfast", "lunch"}:
        mode = "breakfast" if timezone.localtime().time() < time(13, 0) else "lunch"
    visibility = "show_on_table_breakfast" if mode == "breakfast" else "show_on_table_lunch"
    ordering = "table_breakfast_order" if mode == "breakfast" else "table_lunch_order"
    reserved_category_names = ("Comida corrida", "Comida ejecutiva", "Comida por orden")
    categories = list(Category.objects.filter(**{visibility: True}).exclude(
        name__in=reserved_category_names,
    ).order_by(ordering, "name").prefetch_related(Prefetch(
        "products", queryset=Product.objects.filter(is_available=True, is_sold_individually=True).order_by("sort_order", "name"), to_attr="capture_products",
    )))
    categories = [category for category in categories if category.capture_products]
    daily_menu = DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED).select_related(
        "water_product", "chicken_consomme", "variable_first_course", "second_course_one",
        "second_course_two", "chicken_stew", "beef_stew", "varied_stew", "beans_order",
    ).first()
    running_meal_products = []
    executive_meal_products = []
    daily_order_products = []
    if mode == "lunch" and daily_menu:
        first_second_ids = [pk for pk in (
            daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id,
            daily_menu.second_course_one_id, daily_menu.second_course_two_id,
        ) if pk]
        stew_ids = [pk for pk in (
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id,
        ) if pk]
        daily_ids = first_second_ids + stew_ids + ([daily_menu.beans_order_id] if daily_menu.beans_order_id else [])
        daily_records = Product.objects.filter(pk__in=daily_ids, is_available=True)
        daily_by_id = {product.pk: product for product in daily_records}
        running_meal_products = [daily_by_id[pk] for pk in first_second_ids + stew_ids if pk in daily_by_id]
        daily_order_products = [daily_by_id[pk] for pk in daily_ids if pk in daily_by_id]
        executive_meal_products = [daily_by_id[pk] for pk in first_second_ids if pk in daily_by_id] + list(
            Product.objects.filter(
                component_type=Product.ComponentType.GRILL,
                eligible_for_executive_meal=True, is_available=True,
            ).order_by("category__name", "name")
        )
    products = {product.pk: product for category in categories for product in category.capture_products}
    for product in running_meal_products + executive_meal_products + daily_order_products:
        products[product.pk] = product
    selector_records = Product.objects.filter(pk__in=products).prefetch_related("option_groups__options")
    selector_data = {str(product.pk): serialize_product_selector(product) for product in selector_records}
    package_options = []
    if mode == "lunch" and daily_menu:
        package_options = [
            {"package": package, "form": InternalPackageForm(package=package, daily_menu=daily_menu, prefix=f"internal-package-{package.pk}")}
            for package in MealPackage.objects.filter(is_active=True)
        ]
    return render(request, "orders/internal_order_form.html", {
        "form": form, "order": order, "categories": categories,
        "menu_mode": mode, "next_menu_mode": "lunch" if mode == "breakfast" else "breakfast",
        "menu_mode_label": "Desayunos" if mode == "breakfast" else "Comida",
        "next_menu_mode_label": "Cambiar a comida" if mode == "breakfast" else "Cambiar a desayunos",
        "selector_data": selector_data, "ticket": internal_order_ticket(order),
        "daily_menu": daily_menu, "package_options": package_options,
        "running_meal_products": running_meal_products,
        "executive_meal_products": executive_meal_products,
        "daily_order_products": daily_order_products,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_mode_switch(request, order_id):
    mode = request.POST.get("mode")
    if mode in {"breakfast", "lunch"}:
        request.session[INTERNAL_MENU_MODE_KEY] = mode
    return redirect("orders:internal_order_edit", order_id=order_id)


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_type_switch(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    order_type = request.POST.get("order_type")
    if order_type in Order.OrderType.values:
        order.order_type = order_type
        opened_at = timezone.localtime(order.created_at)
        order.requested_date = order.requested_date or opened_at.date()
        order.requested_time = order.requested_time or opened_at.time().replace(second=0, microsecond=0)
        if order_type == Order.OrderType.DELIVERY and not order.neighborhood:
            order.neighborhood = "del valle centro"
        if order_type == Order.OrderType.PICKUP and not order.customer_name.strip():
            order.customer_name = "Mostrador"
        order.save(update_fields=("order_type", "customer_name", "requested_date", "requested_time", "neighborhood", "updated_at"))
    return redirect("orders:internal_order_edit", order_id=order.pk)


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_customer_autosave(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    form = InternalOrderAutosaveForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    order = autosave_internal_order_customer(order=order, form_data=form.cleaned_data)
    phone_key = "".join(character for character in order.phone if character.isdigit())
    duplicate = Customer.objects.filter(phone_key=phone_key).exclude(pk=order.agenda_customer_id).first() if phone_key else None
    return JsonResponse({
        "ok": True, "customer_name": order.customer_name,
        "agenda_customer_id": order.agenda_customer_id,
        "agenda_address_id": order.agenda_address_id,
        "duplicate_customer": ({
            "id": duplicate.pk, "name": duplicate.name, "phone": duplicate.phone,
            "edit_url": reverse("orders:customer_edit", args=(duplicate.pk,)),
            "addresses": [{
                "id": address.pk, "street": address.street,
                "exterior_number": address.exterior_number,
                "interior_number": address.interior_number,
                "neighborhood": address.neighborhood,
                "references": address.references,
            } for address in duplicate.addresses.all()],
        } if duplicate else None),
        "delivery_tip_amount": f"{order.delivery_tip_amount:.2f}",
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_package_extras(request, order_id, item_id):
    order = get_object_or_404(Order, pk=order_id)
    item = get_object_or_404(OrderItem, pk=item_id, order=order, item_type=OrderItem.ItemType.PACKAGE)
    form = InternalPackageExtrasForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Revisa los extras del paquete."}, status=400)
    try:
        update_internal_package_extras(order=order, item=item, cleaned_data=form.cleaned_data)
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_close_capture(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        close_internal_order_capture(order=order, actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("orders:internal_order_edit", order_id=order.pk)
    messages.success(request, f"{order.formatted_number} quedó confirmado y continúa disponible para modificaciones.")
    return redirect("orders:order_list")


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_product_add(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    product = get_object_or_404(Product, pk=product_id)
    upgraded_package = add_water_to_internal_package(order=order, water_product=product)
    if upgraded_package:
        order.refresh_from_db()
        return JsonResponse({
            "ok": True, "ticket": internal_order_ticket(order),
            "message": f"{upgraded_package.package_name_snapshot} ahora incluye agua.",
        })
    try:
        add_internal_order_product(
            order=order, product=product, actor=request.user,
            raw_option_ids=(request.POST.getlist("option_ids") if request.POST.get("customization_selected") == "1" else None),
            comment=(request.POST.get("customization_comment", "") if request.POST.get("customization_selected") == "1" else ""),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_daily_product_add(request, order_id, product_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: Esta ruta vende por separado un componente del
    # menú publicado aunque no forme parte del catálogo individual general. Borra esta nota.
    order = get_object_or_404(Order, pk=order_id)
    product = get_object_or_404(Product, pk=product_id)
    daily_menu = DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED).first()
    allowed_ids = set()
    if daily_menu:
        allowed_ids = {pk for pk in (
            daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id,
            daily_menu.second_course_one_id, daily_menu.second_course_two_id,
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id,
            daily_menu.varied_stew_id, daily_menu.beans_order_id,
        ) if pk}
    if product.pk not in allowed_ids:
        return JsonResponse({"ok": False, "error": "Este producto no pertenece al menú publicado de hoy."}, status=400)
    try:
        add_internal_order_product(
            order=order, product=product, actor=request.user, require_individual=False,
            raw_option_ids=(request.POST.getlist("option_ids") if request.POST.get("customization_selected") == "1" else None),
            comment=(request.POST.get("customization_comment", "") if request.POST.get("customization_selected") == "1" else ""),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_item_change(request, order_id, item_id):
    order = get_object_or_404(Order, pk=order_id)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    try:
        change_internal_order_item(order=order, item=item, action=request.POST.get("action"))
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    clear_internal_auto_meals(request, order.pk)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_note(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    note = request.POST.get("note", "")
    if len(note) > 1000:
        return JsonResponse({"ok": False, "error": "La nota general no puede exceder 1000 caracteres."}, status=400)
    update_internal_order_note(order=order, note=note)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_item_note(request, order_id, item_id):
    order = get_object_or_404(Order, pk=order_id)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    note = request.POST.get("note", "")
    if len(note) > 150:
        return JsonResponse({"ok": False, "error": "La nota del producto no puede exceder 150 caracteres."}, status=400)
    update_internal_order_item_note(order=order, item=item, note=note)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_auto_meal_add(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    product = get_object_or_404(Product, pk=product_id)
    daily_menu = get_object_or_404(
        DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    slot = internal_auto_meal_slot(product, daily_menu)
    if not slot:
        return JsonResponse({"ok": False, "error": "Este producto no puede formar un paquete."}, status=400)
    chicken_piece = request.POST.get("chicken_piece", "")
    all_builders, builders, completed = plan_internal_auto_meal(
        request, order.pk, slot, product.pk, chicken_piece,
    )
    try:
        package_item = add_internal_auto_meal_component(
            order=order, product=product, daily_menu=daily_menu,
            completed_selection=completed, actor=request.user,
            chicken_piece=(completed or {}).get("chicken_piece", chicken_piece),
            raw_option_ids=(request.POST.getlist("option_ids") if request.POST.get("customization_selected") == "1" else None),
            comment=(request.POST.get("customization_comment", "") if request.POST.get("customization_selected") == "1" else ""),
            with_water=request.POST.get("with_water") == "1",
            tortillas=request.POST.get("tortillas") == "1",
            beans=request.POST.get("beans") == "1",
            package_comment=" ".join(request.POST.get("package_comment", "").split()),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    save_internal_auto_meals(request, order.pk, all_builders, builders)
    order.refresh_from_db()
    return JsonResponse({
        "ok": True, "ticket": internal_order_ticket(order),
        "auto_package_created": package_item is not None,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_auto_meal_decrease(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    item = order.items.filter(
        product_id=product_id, item_type=OrderItem.ItemType.PRODUCT,
        is_package_candidate=True, is_customized=False,
    ).order_by("-id").first()
    if item:
        try:
            change_internal_order_item(order=order, item=item, action="decrease")
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        clear_internal_auto_meals(request, order.pk)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_product_decrease(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    product = get_object_or_404(Product.objects.prefetch_related("option_groups__options"), pk=product_id)
    item = order.items.filter(
        product=product, item_type=OrderItem.ItemType.PRODUCT, is_customized=False,
        configuration_signature=resolve_product_selection(product)["signature"],
    ).first()
    if item:
        try:
            change_internal_order_item(order=order, item=item, action="decrease")
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_package_add(request, order_id, package_id):
    order = get_object_or_404(Order, pk=order_id)
    package = get_object_or_404(MealPackage, pk=package_id, is_active=True)
    daily_menu = get_object_or_404(DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
    form = InternalPackageForm(request.POST, package=package, daily_menu=daily_menu, prefix=f"internal-package-{package.pk}")
    if not form.is_valid():
        errors = [error["message"] for values in form.errors.get_json_data().values() for error in values]
        return JsonResponse({"ok": False, "error": " ".join(errors)}, status=400)
    try:
        add_internal_order_package(order=order, package=package, daily_menu=daily_menu, cleaned_data=form.cleaned_data)
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@role_required(*SECTION_ROLE_MATRIX["orders"])
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_history__changed_by"), pk=order_id
    )
    can_manage = user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    actions = [
        {"value": action, "label": ACTION_LABELS[action], "danger": action == "cancel"}
        for action in available_order_actions(order)
    ] if can_manage else []
    return render(request, "orders/order_detail.html", {
        "order": order,
        "order_actions": actions,
        "can_edit_order": can_manage,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def order_resolve(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = transition_order(
            order=order, action=request.POST.get("action"), actor=request.user
        )
    except ValidationError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            action = request.POST.get("action")
            if action == "dispatch_delivery":
                recovery_url = f"{reverse('deliveries:delivery_board')}?q={order.daily_number}"
                recovery_label = "Asignar repartidor"
            else:
                recovery_url = f"{reverse('orders:internal_order_edit', args=(order.pk,))}#payment-methods"
                recovery_label = "Completar pedido"
            return JsonResponse({
                "ok": False, "error": error.message,
                "recovery_url": recovery_url, "recovery_label": recovery_label,
            }, status=400)
        messages.error(request, error.message)
    else:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # NOTA TEMPORAL PARA APRENDIZAJE: devolvemos sólo el estado nuevo y la
            # siguiente transición para actualizar la fila sin recargar. Borra esta nota.
            actions = [action for action in available_order_actions(order) if action != "cancel"]
            next_action = actions[0] if actions else ""
            return JsonResponse({
                "ok": True, "status": order.status,
                "status_label": order.get_status_display(),
                "next_action": next_action,
                "next_action_label": ACTION_LABELS.get(next_action, ""),
            })
        messages.success(request, f"El pedido ahora está: {order.get_status_display()}.")
    if request.POST.get("return_to") == "list":
        return redirect("orders:order_list")
    return redirect("orders:order_detail", order_id=order.pk)


@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def delivery_board(request):
    delivery_orders = Order.objects.filter(
        order_type=Order.OrderType.DELIVERY,
    ).select_related(
        "delivery_person", "delivery_assigned_by", "delivery_tip_recipient",
        "delivery_tip_updated_by",
    )
    repartidores = get_user_model().objects.filter(
        is_active=True, groups__name=DELIVERY,
    ).distinct().order_by("first_name", "username")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    delivery_person = request.GET.get("delivery_person", "").strip()
    if search:
        number_query = _folio_search_query(search)
        delivery_orders = delivery_orders.filter(
            number_query | Q(customer_name__icontains=search) | Q(phone__icontains=search)
            | Q(street__icontains=search) | Q(exterior_number__icontains=search)
            | Q(neighborhood__icontains=search)
        )
    if status in Order.Status.values:
        delivery_orders = delivery_orders.filter(status=status)
    if delivery_person == "unassigned":
        delivery_orders = delivery_orders.filter(delivery_person__isnull=True)
    elif delivery_person.isdigit():
        delivery_orders = delivery_orders.filter(delivery_person_id=int(delivery_person))
    return render(request, "orders/delivery_board.html", {
        "delivery_orders": delivery_orders,
        "repartidores": repartidores,
        "status_choices": Order.Status.choices,
        "search": search, "selected_status": status,
        "selected_delivery_person": delivery_person,
        "can_complete_any": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER, DELIVERY)
def delivery_assign(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    delivery_person = get_object_or_404(
        get_user_model(), pk=request.POST.get("delivery_person")
    )
    try:
        order = assign_delivery(
            order=order, delivery_person=delivery_person, assigned_by=request.user,
        )
    except ValidationError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
    else:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            display_name = order.delivery_person.get_full_name() or order.delivery_person.username
            return JsonResponse({
                "ok": True, "delivery_person_id": order.delivery_person_id,
                "delivery_person_name": display_name,
                "message": f"{display_name} quedó asignado a {order.formatted_number}.",
            })
        messages.success(request, f"El repartidor de {order.formatted_number} fue actualizado.")
    return redirect("deliveries:delivery_board")


@require_POST
@role_required(ADMIN, ORDER_TAKER, DELIVERY)
def delivery_tip_update(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    form = DeliveryTipForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Escribe una propina válida."}, status=400)
    try:
        order = update_delivery_tip(
            order=order, amount=form.cleaned_data["tip_amount"], actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    recipient = "Sin repartidor asignado"
    if order.delivery_tip_recipient:
        recipient = order.delivery_tip_recipient.get_full_name() or order.delivery_tip_recipient.username
    return JsonResponse({
        "ok": True, "tip_amount": f"{order.delivery_tip_amount:.2f}",
        "total_with_tip": f"{order.total_with_delivery_tip:.2f}",
        "recipient": recipient,
    })


@require_POST
@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def delivery_complete(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    action = "dispatch_delivery" if order.status == Order.Status.READY else "complete_delivery"
    try:
        order = transition_order(order=order, action=action, actor=request.user)
    except ValidationError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
    else:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "ok": True, "status": order.status,
                "status_label": order.get_status_display(),
                "next_label": "Marcar como entregado" if order.status == Order.Status.OUT_FOR_DELIVERY else "",
            })
        messages.success(request, f"{order.formatted_number} ahora está: {order.get_status_display()}.")
    return redirect("deliveries:delivery_board")


def _cashier_order_payload(order):
    return {
        "payment_method": order.payment_method,
        "payment_label": order.get_payment_method_display() if order.payment_method else "Sin definir",
        "cash_tendered": f"{order.cash_tendered:.2f}" if order.cash_tendered is not None else "",
        "needs_change": order.needs_change,
        "change_required": f"{order.change_required:.2f}" if order.change_required is not None else "",
        "cash_handoff_confirmed": order.cash_handoff_confirmed,
    }


@role_required(ADMIN)
def cashier_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: Caja sólo carga pedidos operativos; las entregas
    # aparecen primero porque concentran asignación, forma de pago y entrega de cambio.
    # Los filtros ayudan sin convertir este panel en otro historial. Borra esta nota.
    active_statuses = (
        Order.Status.PENDING_CONFIRMATION, Order.Status.CONFIRMED, Order.Status.SCHEDULED,
        Order.Status.PREPARING, Order.Status.READY, Order.Status.OUT_FOR_DELIVERY,
    )
    queryset = Order.objects.filter(status__in=active_statuses).select_related(
        "delivery_person", "cash_handoff_by",
    ).prefetch_related("items").order_by("order_type", "requested_for", "created_at")
    search = request.GET.get("q", "").strip()
    order_type = request.GET.get("type", "").strip()
    if search:
        queryset = queryset.filter(
            _folio_search_query(search) | Q(customer_name__icontains=search)
            | Q(phone__icontains=search) | Q(street__icontains=search)
            | Q(exterior_number__icontains=search)
        )
    if order_type in Order.OrderType.values:
        queryset = queryset.filter(order_type=order_type)
    orders = list(queryset)
    repartidores = get_user_model().objects.filter(
        is_active=True, groups__name=DELIVERY,
    ).distinct().order_by("first_name", "username")
    return render(request, "orders/cashier_board.html", {
        "delivery_orders": [order for order in orders if order.order_type == Order.OrderType.DELIVERY],
        "pickup_orders": [order for order in orders if order.order_type == Order.OrderType.PICKUP],
        "repartidores": repartidores, "search": search, "selected_type": order_type,
    })


@require_POST
@role_required(ADMIN)
def cashier_payment_update(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = update_cashier_payment(
            order=order, payment_method=request.POST.get("payment_method", ""),
            cash_amount=request.POST.get("cash_amount", ""), actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, **_cashier_order_payload(order)})


@require_POST
@role_required(ADMIN)
def cashier_cash_handoff(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = confirm_cash_handoff(
            order=order, actor=request.user,
            confirmed=request.POST.get("confirmed", "1") == "1",
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, **_cashier_order_payload(order)})
