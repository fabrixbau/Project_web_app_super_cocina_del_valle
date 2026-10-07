# NOTA TEMPORAL PARA APRENDIZAJE:
# Retiramos de menu la vista que enviaba paquetes: ahora esa responsabilidad pertenece a
# orders. Aquí solo queda la publicación y configuración del menú. Borra esta nota.
# Los paquetes pueden agendarse antes de comida; el horario genera aviso, no bloqueo.
# El organizador guarda los cinco órdenes completos en una transacción. Borra esta nota.
# La configuración de ingredientes usa familias compartidas: asociar un grupo a varios productos
# hace que una edición central se refleje en todos ellos. Borra esta nota.
# Crear/editar producto guarda ahora la receta completa en la misma transacción mediante un
# payload JSON validado por Django; los IDs existentes se conservan. Borra esta nota.

import json
import random
from collections import defaultdict
from io import BytesIO
from calendar import monthrange
from datetime import date, time, timedelta

from PIL import Image, ImageOps
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from urllib.parse import urlencode
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER, SECTION_ROLE_MATRIX, role_required, user_has_any_role

from .customization import (
    parse_customization_payload, serialize_group, serialize_product_customization,
    sync_product_customization,
)
from .group_library import shared_group_families, sync_shared_group
from .inventory import adjust_stock, daily_menu_stock_errors, filter_products_by_stock

from .forms import (
    CategoryForm, DailyMenuForm, MealPackageForm, ProductForm, ProductOptionForm,
    FixedStockForm, ProductOptionGroupCopyForm, ProductOptionGroupForm,
)
from .models import (
    Category, DailyMenu, DailyProductStock, InventoryAuditLog, MealPackage, Product, ProductOption,
    ProductOptionGroup, ServicePeriod, StockMovement,
)
from .selection import serialize_product_selector


@role_required(*SECTION_ROLE_MATRIX["menu"])
def configuration(request):
    categories = Category.objects.annotate(product_count=Count("products")).order_by("sort_order", "name")
    products = Product.objects.select_related("category").prefetch_related(
        "service_periods",
    ).annotate(option_group_count=Count("option_groups", distinct=True)).order_by(
        "category__sort_order", "category__name", "sort_order", "name",
    )
    search = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    availability = request.GET.get("availability", "").strip()
    product_id = request.GET.get("product", "").strip()
    # Sugerencias de la lupa: todos los productos; elegir uno muestra sólo ése.
    search_options = [
        {
            "label": product.name, "detail": product.category.name,
            "search": f"{product.name} {product.description}",
            "url": f"{reverse('menu:configuration')}?{urlencode({'q': product.name, 'product': product.pk})}",
        }
        for product in Product.objects.select_related("category").only(
            "id", "name", "description", "category__name",
        ).order_by("name")
    ]

    if product_id.isdigit():
        products = products.filter(pk=int(product_id))
    elif search:
        products = products.filter(Q(name__icontains=search) | Q(description__icontains=search))
    if category_id.isdigit():
        products = products.filter(category_id=category_id)
    if availability == "available":
        products = products.filter(is_available=True)
    elif availability == "unavailable":
        products = products.filter(is_available=False)

    return render(request, "menu/configuration.html", {
        "categories": categories,
        "products": products,
        "search": search,
        "selected_category": category_id,
        "availability": availability,
        "search_options": search_options,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def inventory_control(request):
    raw_date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    try:
        selected_date = date.fromisoformat(raw_date)
    except ValueError:
        selected_date = timezone.localdate()
    stocks = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.DAILY, date=selected_date,
    ).select_related(
        "product", "daily_menu",
    ).order_by("item_kind", "product__name", "chicken_piece", "channel")
    fixed_stocks = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.FIXED, is_tracked=True,
    ).select_related("product").order_by("product__category__name", "product__name")
    fixed_form = FixedStockForm(prefix="fixed")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_daily":
            try:
                with transaction.atomic():
                    stock_ids = list(stocks.values_list("pk", flat=True))
                    locked_stocks = DailyProductStock.objects.select_for_update().filter(
                        pk__in=stock_ids,
                    ).order_by("pk")
                    for stock in locked_stocks:
                        raw_quantity = request.POST.get(f"stock_{stock.pk}", "")
                        raw_threshold = request.POST.get(f"threshold_{stock.pk}", "")
                        if not raw_quantity.isdigit() or not raw_threshold.isdigit():
                            raise ValidationError(f"Captura una cantidad válida para {stock.item_name}.")
                        stock.low_stock_threshold = int(raw_threshold)
                        stock.save(update_fields=("low_stock_threshold",))
                        desired = int(raw_quantity)
                        difference = desired - stock.available_quantity
                        if difference:
                            adjust_stock(
                                stock=stock, quantity=difference, actor=request.user,
                                note="Reconteo manual desde el control de inventario diario",
                            )
                        else:
                            from notifications.services import sync_stock_alert
                            sync_stock_alert(stock)
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Las existencias del menú diario fueron actualizadas.")
                return redirect(f"{reverse('menu:inventory_control')}?date={selected_date.isoformat()}")
        elif action == "add_fixed":
            fixed_form = FixedStockForm(request.POST, prefix="fixed")
            if fixed_form.is_valid():
                product = fixed_form.cleaned_data["product"]
                stock, _created = DailyProductStock.objects.get_or_create(
                    stock_type=DailyProductStock.StockType.FIXED,
                    product=product,
                    defaults={
                        "date": None, "channel": DailyProductStock.Channel.SHARED,
                        "initial_quantity": fixed_form.cleaned_data["quantity"],
                        "low_stock_threshold": fixed_form.cleaned_data["low_stock_threshold"],
                    },
                )
                if not _created:
                    difference = fixed_form.cleaned_data["quantity"] - stock.available_quantity
                    stock.is_tracked = True
                    stock.low_stock_threshold = fixed_form.cleaned_data["low_stock_threshold"]
                    stock.save(update_fields=("is_tracked", "low_stock_threshold"))
                    if difference:
                        adjust_stock(
                            stock=stock, quantity=difference, actor=request.user,
                            note="Reactivación o reconteo del producto fijo",
                        )
                from notifications.services import sync_stock_alert
                sync_stock_alert(stock)
                messages.success(request, f"{product.name} quedó bajo control de inventario.")
                return redirect(reverse("menu:inventory_control"))
        elif action == "save_fixed":
            try:
                with transaction.atomic():
                    stock_ids = list(fixed_stocks.values_list("pk", flat=True))
                    locked_stocks = DailyProductStock.objects.select_for_update().filter(
                        pk__in=stock_ids,
                    ).order_by("pk")
                    for stock in locked_stocks:
                        raw_quantity = request.POST.get(f"fixed_stock_{stock.pk}", "")
                        raw_threshold = request.POST.get(f"fixed_threshold_{stock.pk}", "")
                        if not raw_quantity.isdigit() or not raw_threshold.isdigit():
                            raise ValidationError(f"Captura cantidades válidas para {stock.item_name}.")
                        stock.low_stock_threshold = int(raw_threshold)
                        stock.save(update_fields=("low_stock_threshold",))
                        difference = int(raw_quantity) - stock.available_quantity
                        if difference:
                            adjust_stock(
                                stock=stock, quantity=difference, actor=request.user,
                                note="Reconteo manual del inventario fijo",
                            )
                        else:
                            from notifications.services import sync_stock_alert
                            sync_stock_alert(stock)
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "El inventario fijo fue actualizado.")
                return redirect(reverse("menu:inventory_control"))
        elif action == "remove_fixed":
            stock = get_object_or_404(
                DailyProductStock, pk=request.POST.get("stock_id"),
                stock_type=DailyProductStock.StockType.FIXED,
            )
            stock.is_tracked = False
            stock.save(update_fields=("is_tracked",))
            from notifications.services import sync_stock_alert
            sync_stock_alert(stock)
            messages.success(request, f"{stock.item_name} dejó de tener seguimiento de stock.")
            return redirect(reverse("menu:inventory_control"))

    daily_group_map = {}
    for stock in stocks:
        key = (stock.item_kind, stock.product_id, stock.chicken_piece)
        group = daily_group_map.setdefault(key, {
            "label": stock.item_name, "product": stock.product,
            "table": None, "orders": None,
        })
        committed = -(stock.movements.filter(
            reason=StockMovement.Reason.RESERVATION,
        ).aggregate(total=Sum("quantity"))["total"] or 0)
        group[stock.channel] = {
            "stock": stock, "available": stock.available_quantity,
            "committed": committed,
            "status": (
                "empty" if stock.available_quantity == 0
                else "low" if stock.is_low_stock
                else "ok"
            ),
        }
    daily_groups = list(daily_group_map.values())
    for group in daily_groups:
        statuses = {
            row["status"] for row in (group["table"], group["orders"]) if row
        }
        group["status"] = (
            "empty" if "empty" in statuses else "low" if "low" in statuses else "ok"
        )
    fixed_rows = [{
        "stock": stock, "available": stock.available_quantity,
        "committed": -(stock.movements.filter(
            reason=StockMovement.Reason.RESERVATION,
        ).aggregate(total=Sum("quantity"))["total"] or 0),
    } for stock in fixed_stocks]
    return render(request, "menu/inventory_control.html", {
        "selected_date": selected_date, "stock_rows": list(stocks), "daily_groups": daily_groups,
        "fixed_rows": fixed_rows, "fixed_form": fixed_form,
    })


@role_required(ADMIN, ORDER_TAKER, WAITER, DELIVERY)
@never_cache
@transaction.atomic
def inventory_tracking(request):
    # Administrador prevalece; si una cuenta operativa acumuló por error los grupos
    # Mesero/Repartidor y Telefonista, el perfil de campo conserva sólo lectura.
    is_admin = user_has_any_role(request.user, (ADMIN,))
    is_field_profile = user_has_any_role(request.user, (WAITER, DELIVERY))
    can_edit = is_admin or (
        user_has_any_role(request.user, (ORDER_TAKER,)) and not is_field_profile
    )
    if request.method == "POST" and not can_edit:
        raise PermissionDenied
    raw_date = request.POST.get("date") or request.GET.get("date") or timezone.localdate().isoformat()
    try:
        selected_date = date.fromisoformat(raw_date)
    except ValueError:
        selected_date = timezone.localdate()

    stocks = list(DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.DAILY,
        date=selected_date,
        is_tracked=True,
    ).select_related("product", "product__category", "daily_menu"))

    def identity(stock):
        return (stock.item_kind, stock.product_id, stock.chicken_piece)

    if request.method == "POST" and request.POST.get("action") == "set_prepared":
        # Cada canal (Mesas, Pedidos o Compartido) tiene su propio preparado y su propia
        # alerta: el formulario envía prepared_<id> y alert_<id> por cada existencia del
        # producto y sólo se ajusta el canal que cambió.
        stock = get_object_or_404(DailyProductStock, pk=request.POST.get("stock_id"), date=selected_date)
        siblings = [row for row in stocks if identity(row) == identity(stock)]
        try:
            requested = {}
            for sibling in siblings:
                desired = int(request.POST.get(f"prepared_{sibling.pk}", ""))
                alert_threshold = int(request.POST.get(f"alert_{sibling.pk}", str(sibling.low_stock_threshold)))
                if desired < 0 or alert_threshold < 0:
                    raise ValueError
                requested[sibling.pk] = (desired, alert_threshold)
        except ValueError:
            messages.error(request, "Las cantidades preparadas y las alertas deben ser cero o mayores.")
        else:
            from notifications.services import sync_stock_alert
            note = request.POST.get("note", "").strip()
            for sibling in siblings:
                desired, alert_threshold = requested[sibling.pk]
                committed = -(sibling.movements.filter(reason__in=(
                    StockMovement.Reason.RESERVATION, StockMovement.Reason.RELEASE,
                )).aggregate(total=Sum("quantity"))["total"] or 0)
                finalized = -(sibling.movements.filter(
                    reason=StockMovement.Reason.CONSUMPTION,
                ).aggregate(total=Sum("quantity"))["total"] or 0)
                current_prepared = sibling.available_quantity + committed + finalized
                previous_threshold = sibling.low_stock_threshold
                if desired == current_prepared and alert_threshold == previous_threshold:
                    continue
                if desired != current_prepared:
                    adjust_stock(
                        stock=sibling, quantity=desired - current_prepared, actor=request.user,
                        note=note or f"Actualización del preparado de {sibling.get_channel_display()}",
                    )
                if alert_threshold != previous_threshold:
                    sibling.low_stock_threshold = alert_threshold
                    sibling.save(update_fields=("low_stock_threshold", "updated_at"))
                sync_stock_alert(sibling)
                InventoryAuditLog.objects.create(
                    stock=sibling, actor=request.user,
                    prepared_before=current_prepared, prepared_after=desired,
                    threshold_before=previous_threshold, threshold_after=alert_threshold,
                    note=note,
                )
            messages.success(request, f"Existencias y alertas de {stock.item_name} actualizadas.")
        return redirect(f"{reverse('menu:inventory_tracking')}?date={selected_date.isoformat()}")
    if request.method == "POST":
        raise PermissionDenied

    def stock_status(free, threshold):
        return "deficit" if free < 0 else "empty" if free == 0 else "low" if free <= threshold else "ok"

    # Un producto agrupa sus existencias por canal (Mesas, Pedidos o Compartido). El total
    # suma los canales y cada canal conserva sus propias cifras y su alerta.
    channel_order = {
        DailyProductStock.Channel.TABLE: 0,
        DailyProductStock.Channel.ORDERS: 1,
        DailyProductStock.Channel.SHARED: 2,
    }
    groups = {}
    stock_to_key = {}
    channel_rows = {}
    for stock in stocks:
        key = identity(stock)
        stock_to_key[stock.pk] = key
        group = groups.setdefault(key, {
            "name": stock.item_name, "stock": stock, "free": 0, "committed": 0,
            "finalized": 0, "prepared": 0, "threshold": 0, "channels": [],
            "committed_refs": defaultdict(int), "finalized_refs": defaultdict(int),
            "ref_channel": {},
        })
        group["free"] += stock.available_quantity
        channel_rows[stock.pk] = {
            "stock": stock, "channel": stock.channel, "label": stock.get_channel_display(),
            "free": stock.available_quantity, "committed": 0, "finalized": 0,
            "threshold": stock.low_stock_threshold,
        }
        group["channels"].append(channel_rows[stock.pk])

    movements = StockMovement.objects.filter(stock_id__in=stock_to_key).select_related("stock")
    for movement in movements:
        group = groups[stock_to_key[movement.stock_id]]
        channel_row = channel_rows[movement.stock_id]
        ref = (movement.reference_type, movement.reference_id)
        if movement.reason in (StockMovement.Reason.RESERVATION, StockMovement.Reason.RELEASE):
            group["committed"] -= movement.quantity
            channel_row["committed"] -= movement.quantity
            if movement.reference_id:
                group["committed_refs"][ref] -= movement.quantity
                group["ref_channel"][ref] = movement.stock.channel
        elif movement.reason == StockMovement.Reason.CONSUMPTION:
            group["finalized"] -= movement.quantity
            channel_row["finalized"] -= movement.quantity
            if movement.reference_id:
                group["finalized_refs"][ref] -= movement.quantity
                group["ref_channel"][ref] = movement.stock.channel

    from orders.models import OrderItem
    from tables.models import TableAccountItem
    order_item_ids = {ref_id for group in groups.values() for ref_type, ref_id in (*group["committed_refs"], *group["finalized_refs"]) if ref_type == "order_item"}
    table_item_ids = {ref_id for group in groups.values() for ref_type, ref_id in (*group["committed_refs"], *group["finalized_refs"]) if ref_type == "table_item"}
    order_items = {item.pk: item for item in OrderItem.objects.filter(pk__in=order_item_ids).select_related(
        "order", "order__delivery_person",
    )}
    table_items = {item.pk: item for item in TableAccountItem.objects.filter(pk__in=table_item_ids).select_related(
        "account", "account__table", "account__assigned_waiter", "account__closed_by",
    )}

    def user_name(user):
        return (user.get_full_name().strip() or user.username) if user else ""

    def detail(ref, quantity, *, finalized=False):
        ref_type, ref_id = ref
        if ref_type == "order_item" and ref_id in order_items:
            order = order_items[ref_id].order
            responsible = ""
            responsible_label = ""
            if finalized and order.order_type == order.OrderType.DELIVERY and order.delivery_person_id:
                responsible = user_name(order.delivery_person)
                responsible_label = "Repartidor"
            return {"quantity": quantity, "kind": "Pedido", "title": order.formatted_number,
                    "customer": order.customer_name or "Mostrador", "status": order.get_status_display(),
                    "responsible": responsible, "responsible_label": responsible_label,
                    "url": reverse("orders:internal_order_edit", args=(order.pk,))}
        if ref_type == "table_item" and ref_id in table_items:
            account = table_items[ref_id].account
            responsible_user = account.closed_by if finalized else account.assigned_waiter
            return {"quantity": quantity, "kind": "Mesa", "title": str(account.table),
                    "customer": account.customer_name or "Sin nombre", "status": account.get_status_display(),
                    "responsible": user_name(responsible_user),
                    "responsible_label": "Finalizó" if finalized else "Mesero",
                    "url": reverse("tables:table_detail", args=(account.pk,))}
        return None

    rows = []
    search = request.GET.get("q", "").strip().casefold()
    status_filter = request.GET.get("status", "").strip()
    for group in groups.values():
        group["committed"] = max(0, group["committed"])
        group["finalized"] = max(0, group["finalized"])
        group["prepared"] = group["free"] + group["committed"] + group["finalized"]
        group["channels"].sort(key=lambda row: channel_order.get(row["channel"], 9))
        for channel_row in group["channels"]:
            channel_row["committed"] = max(0, channel_row["committed"])
            channel_row["finalized"] = max(0, channel_row["finalized"])
            channel_row["prepared"] = channel_row["free"] + channel_row["committed"] + channel_row["finalized"]
            channel_row["status"] = stock_status(channel_row["free"], channel_row["threshold"])
        group["threshold"] = sum(row["threshold"] for row in group["channels"])
        group["status"] = stock_status(group["free"], group["threshold"])

        def details(refs, finalized=False):
            items = []
            for ref, qty in refs.items():
                if qty > 0 and (item := detail(ref, qty, finalized=finalized)):
                    item["channel"] = group["ref_channel"].get(ref, "")
                    items.append(item)
            return items

        group["committed_details"] = details(group["committed_refs"])
        group["finalized_details"] = details(group["finalized_refs"], finalized=True)
        if search and search not in group["name"].casefold():
            continue
        # El filtro de estado encuentra el producto si el total o cualquiera de sus canales
        # está en ese estado (p. ej. Mesas agotado aunque Pedidos tenga piezas libres).
        if status_filter and status_filter not in {group["status"], *(row["status"] for row in group["channels"])}:
            continue
        rows.append(group)
    first_course_types = {
        Product.ComponentType.CHICKEN_CONSOMME,
        Product.ComponentType.VARIABLE_FIRST_COURSE,
    }
    third_course_types = {
        Product.ComponentType.CHICKEN_STEW,
        Product.ComponentType.BEEF_STEW,
        Product.ComponentType.VARIED_STEW,
        Product.ComponentType.GRILL,
    }

    # Dentro del tercer tiempo: pollo, res, guisado variado y al final plancha. Manda el
    # lugar que ocupa el producto en el menú del día; si no lo hay, su tipo de componente.
    stew_rank_by_component = {
        Product.ComponentType.CHICKEN_STEW: 0,
        Product.ComponentType.BEEF_STEW: 1,
        Product.ComponentType.VARIED_STEW: 2,
    }

    def stew_rank(stock, product, component):
        menu = stock.daily_menu
        if menu and product:
            for rank, stew_id in enumerate(menu.stew_ids):
                if stew_id == product.pk:
                    return rank
        return stew_rank_by_component.get(component, 3)

    def tracking_order(row):
        stock = row["stock"]
        product = stock.product
        component = product.component_type if product else ""
        normalized_name = row["name"].casefold()
        rank = 0
        if component in first_course_types:
            section = 10
        elif component == Product.ComponentType.SECOND_COURSE:
            section = 20
        elif component in third_course_types:
            section = 30
            rank = stew_rank(stock, product, component)
        elif stock.item_kind == DailyProductStock.ItemKind.TORTILLAS:
            section = 40
        elif product and (
            (stock.daily_menu_id and stock.daily_menu.beans_order_id == product.pk)
            or (component == Product.ComponentType.COMPLEMENT and "frijol" in normalized_name)
        ):
            section = 50
        elif component == Product.ComponentType.DAILY_WATER:
            section = 60
        elif stock.item_kind == DailyProductStock.ItemKind.BREAD:
            section = 70
        else:
            section = 80
        return (section, rank, product.sort_order if product else 0, normalized_name)

    rows.sort(key=tracking_order)
    return render(request, "menu/inventory_tracking.html", {
        "selected_date": selected_date, "rows": rows, "search": request.GET.get("q", ""),
        "status_filter": status_filter, "total_committed": sum(row["committed"] for row in rows),
        "total_finalized": sum(row["finalized"] for row in rows),
        "channel_totals": [
            {
                "label": label,
                "committed": sum(ch["committed"] for row in rows for ch in row["channels"] if ch["channel"] == value),
                "finalized": sum(ch["finalized"] for row in rows for ch in row["channels"] if ch["channel"] == value),
            }
            for value, label in DailyProductStock.Channel.choices
            if any(ch["channel"] == value for row in rows for ch in row["channels"])
        ],
        "deficit_count": sum(row["status"] == "deficit" for row in rows),
        "can_edit": can_edit,
    })


@role_required(ADMIN, ORDER_TAKER)
@never_cache
def inventory_audit(request):
    logs = InventoryAuditLog.objects.select_related("stock", "stock__product", "actor")
    search = request.GET.get("q", "").strip()
    if search:
        logs = logs.filter(
            Q(stock__product__name__icontains=search)
            | Q(note__icontains=search)
            | Q(actor__username__icontains=search)
            | Q(actor__first_name__icontains=search)
            | Q(actor__last_name__icontains=search)
        )
    page = Paginator(logs, 40).get_page(request.GET.get("page"))
    return render(request, "menu/inventory_audit.html", {"page": page, "search": search})


@role_required(*SECTION_ROLE_MATRIX["menu"])
def inventory_history(request):
    movements = StockMovement.objects.select_related(
        "stock", "stock__product", "stock__product__category", "actor",
    ).order_by("-created_at", "-pk")

    raw_from = request.GET.get("from", "").strip()
    raw_to = request.GET.get("to", "").strip()
    stock_type = request.GET.get("stock_type", "").strip()
    channel = request.GET.get("channel", "").strip()
    reason = request.GET.get("reason", "").strip()
    search = request.GET.get("q", "").strip()

    try:
        date_from = date.fromisoformat(raw_from) if raw_from else None
    except ValueError:
        date_from = None
    try:
        date_to = date.fromisoformat(raw_to) if raw_to else None
    except ValueError:
        date_to = None

    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    if stock_type in DailyProductStock.StockType.values:
        movements = movements.filter(stock__stock_type=stock_type)
    if channel in DailyProductStock.Channel.values:
        movements = movements.filter(stock__channel=channel)
    if reason in StockMovement.Reason.values:
        movements = movements.filter(reason=reason)
    if search:
        movements = movements.filter(
            Q(stock__product__name__icontains=search)
            | Q(note__icontains=search)
            | Q(actor__username__icontains=search)
        )

    totals = movements.aggregate(
        entries=Sum("quantity", filter=Q(quantity__gt=0)),
        exits=Sum("quantity", filter=Q(quantity__lt=0)),
    )
    paginator = Paginator(movements, 30)
    page = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "menu/inventory_history.html", {
        "page": page,
        "movement_count": paginator.count,
        "entry_total": totals["entries"] or 0,
        "exit_total": abs(totals["exits"] or 0),
        "date_from": date_from,
        "date_to": date_to,
        "selected_stock_type": stock_type,
        "selected_channel": channel,
        "selected_reason": reason,
        "search": search,
        "stock_types": DailyProductStock.StockType.choices,
        "channels": (
            (DailyProductStock.Channel.TABLE, "Mesas"),
            (DailyProductStock.Channel.ORDERS, "Pedidos"),
            (DailyProductStock.Channel.SHARED, "Menú fijo"),
        ),
        "reasons": StockMovement.Reason.choices,
        "query_string": query_params.urlencode(),
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_card_image(request, product_id):
    """Return the exact saved 4:3 crop for the administration card."""
    product = get_object_or_404(Product, pk=product_id)
    if not product.image:
        raise Http404
    with product.image.open("rb") as source:
        image = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        width, height = image.size
        ratio = 4 / 3
        zoom = max(1.0, min(3.0, float(product.image_zoom)))
        position_x = product.image_position_x / 100
        position_y = product.image_position_y / 100
        if width / height > ratio:
            base_height = height
            base_width = base_height * ratio
            base_left = (width - base_width) * position_x
            base_top = 0
        else:
            base_width = width
            base_height = base_width / ratio
            base_left = 0
            base_top = (height - base_height) * position_y
        crop_width = base_width / zoom
        crop_height = base_height / zoom
        left = base_left + base_width * position_x * (1 - 1 / zoom)
        top = base_top + base_height * position_y * (1 - 1 / zoom)
        left = max(0, min(width - crop_width, left))
        top = max(0, min(height - crop_height, top))
        image = image.crop((round(left), round(top), round(left + crop_width), round(top + crop_height)))
        image.thumbnail((900, 675), Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=88, method=4)
    response = HttpResponse(output.getvalue(), content_type="image/webp")
    # El encuadre puede cambiar sin reemplazar el archivo original. No permitimos
    # que el navegador reutilice durante cinco minutos una miniatura anterior y
    # haga parecer que X/Y/zoom no se guardaron.
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    return response


@role_required(*SECTION_ROLE_MATRIX["menu"])
def category_ordering(request):
    categories = list(Category.objects.annotate(product_count=Count("products")))
    category_ids = {category.pk for category in categories}
    order_fields = {
        "general_order": "sort_order",
        "public_breakfast_order": "public_breakfast_order",
        "public_lunch_order": "public_lunch_order",
        "breakfast_order": "table_breakfast_order",
        "lunch_order": "table_lunch_order",
    }
    visibility_fields = {
        "public_breakfast_visible": "show_on_public_breakfast",
        "public_lunch_visible": "show_on_public_lunch",
    }
    if request.method == "POST":
        valid_orders = {}
        for input_name in order_fields:
            try:
                parsed_ids = [int(value) for value in request.POST.getlist(input_name)]
            except (TypeError, ValueError):
                parsed_ids = []
            if len(parsed_ids) != len(category_ids) or set(parsed_ids) != category_ids:
                messages.error(
                    request,
                    "El orden recibido está incompleto. Recarga la pantalla e inténtalo otra vez.",
                )
                return redirect("menu:category_ordering")
            valid_orders[input_name] = parsed_ids

        categories_by_id = {category.pk: category for category in categories}
        visible_category_ids = {}
        for input_name in visibility_fields:
            try:
                parsed_ids = {int(value) for value in request.POST.getlist(input_name)}
            except (TypeError, ValueError):
                parsed_ids = set()
            if not parsed_ids.issubset(category_ids):
                messages.error(request, "La visibilidad recibida no corresponde a las categorías actuales.")
                return redirect("menu:category_ordering")
            visible_category_ids[input_name] = parsed_ids
        with transaction.atomic():
            for input_name, field_name in order_fields.items():
                for position, category_id in enumerate(valid_orders[input_name], start=1):
                    setattr(categories_by_id[category_id], field_name, position * 10)
            for input_name, field_name in visibility_fields.items():
                for category in categories:
                    setattr(category, field_name, category.pk in visible_category_ids[input_name])
            Category.objects.bulk_update(
                categories,
                (
                    "sort_order", "public_breakfast_order", "public_lunch_order",
                    "table_breakfast_order", "table_lunch_order",
                    "show_on_public_breakfast", "show_on_public_lunch",
                ),
            )
        messages.success(request, "Los cinco órdenes de categorías fueron actualizados.")
        return redirect("menu:category_ordering")

    return render(request, "menu/category_ordering.html", {
        "general_categories": sorted(categories, key=lambda item: (item.sort_order, item.name)),
        "public_breakfast_categories": sorted(
            categories, key=lambda item: (item.public_breakfast_order, item.name),
        ),
        "public_lunch_categories": sorted(
            categories, key=lambda item: (item.public_lunch_order, item.name),
        ),
        "breakfast_categories": sorted(
            categories, key=lambda item: (item.table_breakfast_order, item.name),
        ),
        "lunch_categories": sorted(
            categories, key=lambda item: (item.table_lunch_order, item.name),
        ),
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def category_create(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        messages.success(request, f"La categoría {category.name} fue creada.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {
        "form": form, "title": "Nueva categoría", "show_category_order_link": True,
        "is_category_form": True,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La categoría fue actualizada.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {
        "form": form, "title": f"Editar categoría: {category.name}",
        "show_category_order_link": True, "is_category_form": True,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    has_products = category.products.exists()
    if request.method == "POST":
        if has_products:
            messages.error(request, "No puedes eliminar una categoría que contiene productos.")
        else:
            name = category.name
            category.delete()
            messages.success(request, f"La categoría {name} fue eliminada.")
        return redirect("menu:configuration")
    return render(request, "menu/confirm_delete.html", {
        "object": category, "object_type": "categoría", "blocked": has_products,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    customization_data, clean_groups = customization_submission(request, form)
    if request.method == "POST" and form.is_valid() and clean_groups is not None:
        with transaction.atomic():
            product = form.save()
            sync_product_customization(product, clean_groups)
        messages.success(request, f"El producto {product.name} y sus ingredientes fueron creados.")
        return redirect("menu:configuration")
    if request.method == "POST":
        messages.error(request, "No se pudo crear el producto. Revisa los campos marcados.")
    category_next_orders = {
        str(category["id"]): (
            category["maximum_order"] + 1
            if category["maximum_order"] is not None else 0
        )
        for category in Category.objects.annotate(
            maximum_order=Max("products__sort_order"),
        ).values("id", "maximum_order")
    }
    return render(request, "menu/form.html", {
        "form": form, "title": "Nuevo producto", "is_product_form": True,
        "is_product_create": True, "category_next_orders": category_next_orders,
        "customization_data": customization_data,
        "customization_library": customization_group_library(),
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_edit(request, product_id):
    product = get_object_or_404(
        Product.objects.prefetch_related("option_groups__options"), id=product_id,
    )
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    customization_data, clean_groups = customization_submission(request, form, product=product)
    if request.method == "POST" and form.is_valid() and clean_groups is not None:
        with transaction.atomic():
            product = form.save()
            sync_product_customization(product, clean_groups)
        messages.success(request, "El producto y sus ingredientes fueron actualizados.")
        return redirect("menu:configuration")
    if request.method == "POST":
        messages.error(request, "No se pudo actualizar el producto. Revisa los campos marcados.")
    return render(request, "menu/form.html", {
        "form": form, "title": f"Editar producto: {product.name}", "is_product_form": True,
        "is_product_create": False,
        "customization_data": customization_data,
        "customization_library": customization_group_library(exclude_product=product),
    })


def customization_submission(request, form, product=None):
    if request.method != "POST":
        return (serialize_product_customization(product) if product else []), []
    raw_payload = request.POST.get("customization_data", "[]")
    try:
        display_data = json.loads(raw_payload)
        if not isinstance(display_data, list):
            display_data = []
    except (TypeError, json.JSONDecodeError):
        display_data = []
    try:
        clean_groups = parse_customization_payload(raw_payload)
    except ValidationError as error:
        form.add_error(None, error.message)
        clean_groups = None
    return display_data, clean_groups


def customization_group_library(exclude_product=None):
    groups = ProductOptionGroup.objects.select_related("product").prefetch_related(
        "options",
    ).order_by("product__name", "sort_order", "name")
    if exclude_product:
        attached_keys = exclude_product.option_groups.values_list("shared_key", flat=True)
        groups = groups.exclude(product=exclude_product).exclude(shared_key__in=attached_keys)
    unique_groups = {}
    for group in groups:
        unique_groups.setdefault(group.shared_key, group)
    return [serialize_group(group, as_template=True) for group in unique_groups.values()]


@role_required(*SECTION_ROLE_MATRIX["menu"])
def ingredient_group_library(request):
    return render(request, "menu/ingredient_group_library.html", {
        "families": shared_group_families(),
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def shared_group_edit(request, shared_key=None):
    representative = None
    if shared_key:
        representative = ProductOptionGroup.objects.prefetch_related("options").filter(
            shared_key=shared_key,
        ).order_by("id").first()
        if representative is None:
            raise Http404("El grupo compartido no existe.")
    errors = []
    selected_product_ids = (
        {group.product_id for group in ProductOptionGroup.objects.filter(shared_key=shared_key)}
        if representative else set()
    )
    customization_data = [serialize_group(representative)] if representative else [{
        "id": None, "shared_key": None, "name": "", "selection_type": "multiple",
        "is_required": False, "options": [{
            "id": None, "name": "", "price_adjustment": "0.00", "replacement_pair": "",
            "is_default": False, "is_available": True,
        }],
    }]
    if request.method == "POST":
        selected_product_ids = {
            int(value) for value in request.POST.getlist("products") if value.isdigit()
        }
        raw_payload = request.POST.get("customization_data", "[]")
        try:
            customization_data = json.loads(raw_payload)
            clean_groups = parse_customization_payload(raw_payload)
            if len(clean_groups) != 1:
                raise ValidationError("Este editor debe contener exactamente un grupo compartido.")
            family_key = sync_shared_group(
                clean_groups[0], selected_product_ids,
                shared_key=representative.shared_key if representative else None,
            )
        except (ValidationError, json.JSONDecodeError, TypeError) as error:
            errors = error.messages if isinstance(error, ValidationError) else ["No fue posible leer el grupo."]
        else:
            messages.success(request, "El grupo y todos sus productos asociados fueron actualizados.")
            return redirect("menu:shared_group_edit", shared_key=family_key)
    return render(request, "menu/shared_group_form.html", {
        "representative": representative,
        "customization_data": customization_data,
        "customization_library": [],
        "products": Product.objects.select_related("category").order_by("category__name", "name"),
        "selected_product_ids": selected_product_ids,
        "errors": errors,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_customization(request, product_id):
    get_object_or_404(Product, pk=product_id)
    return redirect(f"{reverse('menu:product_edit', args=(product_id,))}#product-ingredients")


@role_required(*SECTION_ROLE_MATRIX["menu"])
def option_group_form(request, product_id, group_id=None):
    product = get_object_or_404(Product, pk=product_id)
    group = (
        get_object_or_404(ProductOptionGroup, pk=group_id, product=product)
        if group_id else ProductOptionGroup(product=product)
    )
    form = ProductOptionGroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El grupo de ingredientes fue guardado.")
        return redirect("menu:product_customization", product_id=product.pk)
    return render(request, "menu/customization_form.html", {
        "form": form, "product": product,
        "title": "Editar grupo" if group_id else "Nuevo grupo de ingredientes",
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def option_group_copy(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    form = ProductOptionGroupCopyForm(request.POST or None, target_product=product)
    if request.method == "POST" and form.is_valid():
        source = form.cleaned_data["source_group"]
        if ProductOptionGroup.objects.filter(product=product, name__iexact=source.name).exists():
            form.add_error(
                "source_group", f"{product.name} ya tiene un grupo llamado {source.name}.",
            )
        else:
            with transaction.atomic():
                copied_group = ProductOptionGroup.objects.create(
                    product=product,
                    shared_key=source.shared_key,
                    name=source.name,
                    selection_type=ProductOptionGroup.SelectionType.MULTIPLE,
                    is_required=source.is_required,
                    sort_order=source.sort_order,
                )
                ProductOption.objects.bulk_create([
                    ProductOption(
                        group=copied_group,
                        name=option.name,
                        price_adjustment=option.price_adjustment,
                        is_default=option.is_default,
                        is_available=option.is_available,
                        replacement_pair=option.replacement_pair,
                        sort_order=option.sort_order,
                    )
                    for option in source.options.all()
                ])
            messages.success(
                request, f"El grupo {source.name} fue copiado desde {source.product.name}.",
            )
            return redirect("menu:product_customization", product_id=product.pk)
    return render(request, "menu/customization_form.html", {
        "form": form, "product": product, "title": "Pegar grupo existente",
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
@require_POST
def option_group_delete(request, product_id, group_id):
    product = get_object_or_404(Product, pk=product_id)
    group = get_object_or_404(ProductOptionGroup, pk=group_id, product=product)
    name = group.name
    group.delete()
    messages.success(request, f"El grupo {name} fue eliminado.")
    return redirect("menu:product_customization", product_id=product.pk)


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_option_form(request, product_id, group_id, option_id=None):
    product = get_object_or_404(Product, pk=product_id)
    group = get_object_or_404(ProductOptionGroup, pk=group_id, product=product)
    option = (
        get_object_or_404(ProductOption, pk=option_id, group=group)
        if option_id else ProductOption(group=group)
    )
    form = ProductOptionForm(request.POST or None, instance=option)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El ingrediente u opción fue guardado.")
        return redirect("menu:product_customization", product_id=product.pk)
    return render(request, "menu/customization_form.html", {
        "form": form, "product": product, "group": group,
        "title": "Editar ingrediente" if option_id else f"Nuevo ingrediente · {group.name}",
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
@require_POST
def product_option_delete(request, product_id, group_id, option_id):
    product = get_object_or_404(Product, pk=product_id)
    group = get_object_or_404(ProductOptionGroup, pk=group_id, product=product)
    option = get_object_or_404(ProductOption, pk=option_id, group=group)
    name = option.name
    option.delete()
    messages.success(request, f"La opción {name} fue eliminada.")
    return redirect("menu:product_customization", product_id=product.pk)


@role_required(*SECTION_ROLE_MATRIX["menu"])
@require_POST
def product_toggle_availability(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_available = not product.is_available
    product.save(update_fields=["is_available", "updated_at"])
    state = "disponible" if product.is_available else "no disponible"
    messages.success(request, f"{product.name} ahora está {state}.")
    return redirect("menu:configuration")


@role_required(*SECTION_ROLE_MATRIX["menu"])
@require_POST
def product_toggle_customer_visibility(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.show_to_customers = not product.show_to_customers
    product.save(update_fields=["show_to_customers", "updated_at"])
    state = "visible" if product.show_to_customers else "oculto"
    messages.success(request, f"{product.name} ahora está {state} para clientes.")
    next_url = request.POST.get("next", "")
    if next_url.startswith("/app/menu/"):
        return redirect(next_url)
    return redirect("menu:configuration")


def _product_delete_blocker(product):
    # NOTA TEMPORAL PARA APRENDIZAJE: DailyMenu protege sus 9 componentes (agua,
    # consomé, tiempos, guisados, complemento) y DailyProductStock protege su
    # producto con on_delete=PROTECT, a propósito, para no perder el histórico de
    # menús/inventario ya publicados. Antes de este arreglo, intentar borrar un
    # producto usado en cualquiera de esos lugares tiraba un ProtectedError sin
    # capturar y el usuario veía un error 500. Borra esta nota después de leerla.
    daily_menu_relations = (
        "daily_menus_as_water", "daily_menus_as_chicken_consomme", "daily_menus_as_variable_first_course",
        "daily_menus_as_second_course_one", "daily_menus_as_second_course_two",
        "daily_menu_stew_entries", "daily_menus_as_beans_order",
    )
    if any(getattr(product, relation).exists() for relation in daily_menu_relations):
        return "está asignado como componente en uno o más menús diarios"
    if product.daily_stocks.exists():
        return "tiene existencias registradas en el inventario diario"
    return ""


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    blocked_reason = _product_delete_blocker(product)
    if request.method == "POST":
        if blocked_reason:
            messages.error(request, f"No puedes eliminar {product.name} porque {blocked_reason}.")
            return redirect("menu:configuration")
        name = product.name
        try:
            product.delete()
        except ProtectedError:
            messages.error(request, f"No puedes eliminar {name} porque está en uso en otros registros.")
            return redirect("menu:configuration")
        messages.success(request, f"El producto {name} fue eliminado.")
        return redirect("menu:configuration")
    return render(request, "menu/confirm_delete.html", {
        "object": product, "object_type": "producto", "blocked": bool(blocked_reason),
        "blocked_reason": blocked_reason,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def daily_menu_list(request):
    requested_month = request.GET.get("month", "")
    try:
        selected_month = date.fromisoformat(f"{requested_month}-01") if requested_month else timezone.localdate().replace(day=1)
    except ValueError:
        selected_month = timezone.localdate().replace(day=1)
    last_day = monthrange(selected_month.year, selected_month.month)[1]
    month_end = selected_month.replace(day=last_day)
    previous_month = (selected_month.replace(day=1) - timedelta(days=1)).replace(day=1)
    next_month = (month_end + timedelta(days=1)).replace(day=1)
    daily_menus = DailyMenu.objects.filter(
        date__range=(selected_month, month_end),
    ).select_related(
        "water_product", "chicken_consomme", "variable_first_course",
        "second_course_one", "second_course_two", "beans_order",
    ).prefetch_related("stew_entries__product")
    return render(request, "menu/daily_menu_list.html", {
        "daily_menus": daily_menus,
        "selected_month": selected_month,
        "previous_month": previous_month,
        "next_month": next_month,
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
def daily_menu_form(request, daily_menu_id=None):
    daily_menu = get_object_or_404(DailyMenu, id=daily_menu_id) if daily_menu_id else DailyMenu()
    form = DailyMenuForm(request.POST or None, instance=daily_menu)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
                form.save_stocks()
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "El menú diario y sus raciones fueron guardados.")
            return redirect("menu:daily_menu_list")

    return render(request, "menu/daily_menu_form.html", {
        "form": form,
        "daily_menu": daily_menu,
        "title": "Editar menú diario" if daily_menu.pk else "Nuevo menú diario",
    })


@role_required(*SECTION_ROLE_MATRIX["menu"])
@require_POST
def daily_menu_status(request, daily_menu_id):
    daily_menu = get_object_or_404(DailyMenu, id=daily_menu_id)
    action = request.POST.get("action")

    if action == "publish":
        required_field_names = (
            "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two",
        )
        selected_products = [getattr(daily_menu, field_name) for field_name in required_field_names]
        if any(product is None for product in selected_products) or not daily_menu.stew_ids:
            messages.error(request, "Completa el agua, las sopas, el segundo tiempo y al menos un guisado antes de publicar.")
        elif daily_menu.second_course_one_id == daily_menu.second_course_two_id:
            messages.error(request, "Las dos opciones del segundo tiempo deben ser diferentes.")
        elif any(not product.is_available for product in selected_products):
            messages.error(request, "Todos los productos seleccionados deben estar disponibles.")
        elif missing_stock := daily_menu_stock_errors(daily_menu):
            messages.error(
                request,
                "Completa la distribución de raciones antes de publicar: " + ", ".join(missing_stock) + ".",
            )
        else:
            daily_menu.status = DailyMenu.Status.PUBLISHED
            daily_menu.published_at = timezone.now()
            daily_menu.save(update_fields=["status", "published_at", "updated_at"])
            messages.success(request, "El menú diario fue publicado.")
    elif action == "close":
        daily_menu.status = DailyMenu.Status.CLOSED
        daily_menu.save(update_fields=["status", "updated_at"])
        messages.success(request, "El menú diario fue cerrado.")
    elif action == "draft":
        daily_menu.status = DailyMenu.Status.DRAFT
        daily_menu.published_at = None
        daily_menu.save(update_fields=["status", "published_at", "updated_at"])
        messages.success(request, "El menú volvió a borrador.")

    month = request.POST.get("month", "")
    try:
        date.fromisoformat(f"{month}-01")
    except ValueError:
        return redirect("menu:daily_menu_list")
    return redirect(f"{reverse('menu:daily_menu_list')}?month={month}")


@role_required(*SECTION_ROLE_MATRIX["menu"])
def package_configuration(request):
    packages = list(MealPackage.objects.all())
    forms = [MealPackageForm(
        request.POST or None, instance=package, prefix=f"package-{package.pk}"
    ) for package in packages]
    if request.method == "POST" and forms and all(form.is_valid() for form in forms):
        for form in forms:
            form.save()
        messages.success(request, "La configuración de los paquetes fue actualizada.")
        return redirect("menu:package_configuration")
    return render(request, "menu/package_configuration.html", {"package_forms": forms})


def public_menu(request):
    from orders.cart import get_order_mode, set_order_mode

    requested_mode = request.GET.get("modalidad")
    if requested_mode in {"pickup", "delivery"}:
        # La portada envía la modalidad elegida; se guarda y se limpia la URL.
        set_order_mode(request.session, requested_mode)
        return redirect("public_portal:menu")
    if not get_order_mode(request.session):
        return redirect("public_portal:home")
    from public_portal.preview import public_time

    current_time = public_time(request.session)
    public_mode = "breakfast" if current_time < time(12, 30) else "lunch"
    public_visibility_field = (
        "show_on_public_breakfast" if public_mode == "breakfast" else "show_on_public_lunch"
    )
    public_order_field = (
        "public_breakfast_order" if public_mode == "breakfast" else "public_lunch_order"
    )
    active_periods = ServicePeriod.objects.filter(
        is_active=True,
        start_time__lte=current_time,
        end_time__gte=current_time,
    )
    daily_component_types = (
        Product.ComponentType.CHICKEN_CONSOMME,
        Product.ComponentType.VARIABLE_FIRST_COURSE,
        Product.ComponentType.SECOND_COURSE,
        Product.ComponentType.CHICKEN_STEW,
        Product.ComponentType.BEEF_STEW,
        Product.ComponentType.VARIED_STEW,
    )
    base_public_products = (
        Product.objects.filter(
            is_available=True, is_sold_individually=True, show_to_customers=True,
            packaging_kind=Product.PackagingKind.NONE,
        )
        .exclude(component_type__in=daily_component_types)
    )
    # El portal sigue sus dos interfaces operativas (7:00–12:30 y 12:31–18:00).
    # La visibilidad pública de la categoría decide el catálogo; los periodos internos
    # no deben apagar comida a las 17:00 cuando el portal continúa hasta las 18:00.
    available_now = base_public_products.distinct().order_by("sort_order", "name")

    def visible_category_list(visibility_field, order_field, products):
        queryset = Category.objects.filter(**{visibility_field: True}).order_by(
            order_field, "name",
        ).prefetch_related(Prefetch("products", queryset=products, to_attr="available_products"))
        return [category for category in queryset if category.available_products]

    # Un solo menú a cualquier hora (el de comida): paquetes y productos de comida se pueden
    # pedir desde la mañana (se entregan a partir de la 1:00 p. m.). Las categorías sólo de
    # desayuno (visibles en desayuno pero no en comida) van primero hasta las 12:30 y
    # después se ocultan.
    lunch_categories = visible_category_list("show_on_public_lunch", "public_lunch_order", available_now)
    breakfast_only_categories = []
    if public_mode == "breakfast":
        breakfast_only_categories = [
            category for category in visible_category_list(
                "show_on_public_breakfast", "public_breakfast_order", available_now,
            )
            if not category.show_on_public_lunch
        ]
    visible_categories = [*breakfast_only_categories, *lunch_categories]
    advance_lunch_categories = []
    from .catalog import limit_cold_drinks_to_daily_water, public_daily_menu

    daily_menu, daily_groups = public_daily_menu()

    visible_categories = limit_cold_drinks_to_daily_water(
        visible_categories, daily_menu, "available_products",
    )
    advance_lunch_categories = limit_cold_drinks_to_daily_water(
        advance_lunch_categories, daily_menu, "available_products",
    )
    for category in [*visible_categories, *advance_lunch_categories]:
        category.available_products = filter_products_by_stock(
            category.available_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.ORDERS,
        )
    # Pizarra con pestañas: el tercer tiempo de la Comida ejecutiva son los platillos de
    # plancha elegibles. Se destacan 3 al azar, fijos durante todo el día (semilla = fecha),
    # y el resto se muestra al tocar "+N opciones más".
    meal_packages = list(MealPackage.objects.filter(is_active=True))
    executive_featured, executive_more = [], []
    if daily_menu and any(package.package_type == MealPackage.PackageType.EXECUTIVE for package in meal_packages):
        grill_options = filter_products_by_stock(
            list(Product.objects.filter(
                component_type=Product.ComponentType.GRILL, eligible_for_executive_meal=True,
                is_available=True, show_to_customers=True,
            ).order_by("name")),
            daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS,
        )
        featured_ids = {
            product.pk for product in random.Random(daily_menu.date.toordinal()).sample(grill_options, min(3, len(grill_options)))
        }
        executive_featured = [product for product in grill_options if product.pk in featured_ids]
        executive_more = [product for product in grill_options if product.pk not in featured_ids]

    all_rendered_categories = [*visible_categories, *advance_lunch_categories]
    selector_product_ids = {
        product.pk for category in all_rendered_categories for product in category.available_products
    }
    selector_product_ids.update(
        product.pk for group in daily_groups for product in group["products"]
    )
    selector_products = Product.objects.filter(pk__in=selector_product_ids).prefetch_related(
        "option_groups__options",
    )
    product_customizations = {
        str(product.pk): serialize_product_selector(product) for product in selector_products
    }
    customizable_ids = {int(product_id) for product_id in product_customizations}
    for category in all_rendered_categories:
        for product in category.available_products:
            product.has_customization = product.pk in customizable_ids
    for group in daily_groups:
        for product in group["products"]:
            product.has_customization = product.pk in customizable_ids

    from orders.cart import cart_control_summary
    cart_controls = cart_control_summary(request.session)

    return render(request, "menu/public_menu.html", {
        "categories": visible_categories,
        "breakfast_only_categories": breakfast_only_categories,
        "lunch_categories": lunch_categories,
        "advance_lunch_categories": advance_lunch_categories,
        "daily_menu": daily_menu,
        "daily_groups": daily_groups,
        "active_periods": active_periods,
        "meal_packages": meal_packages,
        "running_package": next((package for package in meal_packages if package.package_type == MealPackage.PackageType.RUNNING), None),
        "executive_package": next((package for package in meal_packages if package.package_type == MealPackage.PackageType.EXECUTIVE), None),
        "executive_featured": executive_featured,
        "executive_more": executive_more,
        "advance_food_order": current_time < time(13, 0),
        "public_menu_mode_label": "Desayunos" if public_mode == "breakfast" else "Comida",
        "public_menu_mode": public_mode,
        "product_customizations": product_customizations,
        "cart_controls": cart_controls,
    })
