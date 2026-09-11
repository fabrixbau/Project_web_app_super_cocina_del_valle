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
from io import BytesIO
from calendar import monthrange
from datetime import date, time, timedelta

from PIL import Image, ImageOps
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import SECTION_ROLE_MATRIX, role_required

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
    Category, DailyMenu, DailyProductStock, MealPackage, Product, ProductOption,
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

    if search:
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
    response["Cache-Control"] = "private, max-age=300"
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
                    selection_type=source.selection_type,
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
def product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f"El producto {name} fue eliminado.")
        return redirect("menu:configuration")
    return render(request, "menu/confirm_delete.html", {
        "object": product, "object_type": "producto", "blocked": False,
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
        "second_course_one", "second_course_two", "chicken_stew", "beef_stew",
        "varied_stew", "beans_order",
    )
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
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
        )
        selected_products = [getattr(daily_menu, field_name) for field_name in required_field_names]
        if any(product is None for product in selected_products):
            messages.error(request, "Completa el agua y los siete lugares del menú antes de publicar.")
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
    if request.session.get("public_order_mode") not in {"pickup", "delivery"}:
        return redirect("public_portal:order_mode")
    current_time = timezone.localtime().time()
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
            is_available=True, is_sold_individually=True,
            packaging_kind=Product.PackagingKind.NONE,
        )
        .exclude(component_type__in=daily_component_types)
    )
    # El portal sigue sus dos interfaces operativas (7:00–12:30 y 12:31–18:00).
    # La visibilidad pública de la categoría decide el catálogo; los periodos internos
    # no deben apagar comida a las 17:00 cuando el portal continúa hasta las 18:00.
    available_now = base_public_products.distinct().order_by("sort_order", "name")
    advance_lunch_products = base_public_products.distinct().order_by("sort_order", "name")

    def visible_category_list(visibility_field, order_field, products):
        queryset = Category.objects.filter(**{visibility_field: True}).order_by(
            order_field, "name",
        ).prefetch_related(Prefetch("products", queryset=products, to_attr="available_products"))
        return [category for category in queryset if category.available_products]

    breakfast_categories = visible_category_list(
        "show_on_public_breakfast", "public_breakfast_order", available_now,
    )
    lunch_categories = visible_category_list(
        "show_on_public_lunch", "public_lunch_order",
        advance_lunch_products if public_mode == "breakfast" else available_now,
    )
    # Aunque una categoría esté habilitada en ambos modos, las familias llamadas
    # “Comida …” pertenecen al bloque adelantado inferior durante desayuno.
    breakfast_categories = [
        category for category in breakfast_categories
        if not category.name.casefold().startswith("comida ")
    ]
    visible_categories = breakfast_categories if public_mode == "breakfast" else lunch_categories
    advance_lunch_categories = lunch_categories if public_mode == "breakfast" else []
    daily_menu = (
        DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        .select_related(
            "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
        )
        .first()
    )
    from .catalog import limit_cold_drinks_to_daily_water

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
    daily_groups = []
    if daily_menu:
        group_products = (
            ("Primer tiempo", (daily_menu.chicken_consomme, daily_menu.variable_first_course)),
            ("Segundo tiempo", (daily_menu.second_course_one, daily_menu.second_course_two)),
            ("Guisados", (daily_menu.chicken_stew, daily_menu.beef_stew, daily_menu.varied_stew)),
        )
        for title, products in group_products:
            visible_products = filter_products_by_stock(
                [product for product in products if product and product.is_available],
                daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS,
            )
            if visible_products:
                daily_groups.append({"title": title, "products": visible_products})

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
        "advance_lunch_categories": advance_lunch_categories,
        "daily_menu": daily_menu,
        "daily_groups": daily_groups,
        "active_periods": active_periods,
        "meal_packages": MealPackage.objects.filter(is_active=True),
        "advance_food_order": current_time < time(13, 0),
        "public_menu_mode_label": "Desayunos" if public_mode == "breakfast" else "Comida",
        "public_menu_mode": public_mode,
        "product_customizations": product_customizations,
        "cart_controls": cart_controls,
    })
