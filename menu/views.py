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
from datetime import time

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404
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

from .forms import (
    CategoryForm, DailyMenuForm, MealPackageForm, ProductForm, ProductOptionForm,
    ProductOptionGroupCopyForm, ProductOptionGroupForm,
)
from .models import (
    Category, DailyMenu, MealPackage, Product, ProductOption, ProductOptionGroup,
    ServicePeriod,
)
from .selection import serialize_product_selector


@role_required(*SECTION_ROLE_MATRIX["menu"])
def configuration(request):
    categories = Category.objects.annotate(product_count=Count("products"))
    products = Product.objects.select_related("category").prefetch_related(
        "service_periods",
    ).annotate(option_group_count=Count("option_groups", distinct=True))
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
        "show_category_order_link": True,
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
    return render(request, "menu/form.html", {
        "form": form, "title": "Nuevo producto", "is_product_form": True,
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
    return render(request, "menu/form.html", {
        "form": form, "title": f"Editar producto: {product.name}", "is_product_form": True,
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
    daily_menus = DailyMenu.objects.select_related("water_product")
    return render(request, "menu/daily_menu_list.html", {"daily_menus": daily_menus})


@role_required(*SECTION_ROLE_MATRIX["menu"])
def daily_menu_form(request, daily_menu_id=None):
    daily_menu = get_object_or_404(DailyMenu, id=daily_menu_id) if daily_menu_id else DailyMenu()
    form = DailyMenuForm(request.POST or None, instance=daily_menu)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El menú diario fue guardado.")
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

    return redirect("menu:daily_menu_list")


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
    available_products = (
        Product.objects.filter(is_available=True)
        .exclude(component_type__in=daily_component_types)
        .filter(Q(service_periods__isnull=True) | Q(service_periods__in=active_periods))
        .distinct()
        .order_by("sort_order", "name")
    )
    categories = Category.objects.filter(**{public_visibility_field: True}).order_by(
        public_order_field, "name",
    ).prefetch_related(
        Prefetch("products", queryset=available_products, to_attr="available_products")
    )
    visible_categories = [category for category in categories if category.available_products]
    daily_menu = (
        DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        .select_related(
            "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
        )
        .first()
    )
    daily_groups = []
    if daily_menu:
        group_products = (
            ("Primer tiempo", (daily_menu.chicken_consomme, daily_menu.variable_first_course)),
            ("Segundo tiempo", (daily_menu.second_course_one, daily_menu.second_course_two)),
            ("Guisados", (daily_menu.chicken_stew, daily_menu.beef_stew, daily_menu.varied_stew)),
        )
        for title, products in group_products:
            visible_products = [product for product in products if product and product.is_available]
            if visible_products:
                daily_groups.append({"title": title, "products": visible_products})

    selector_product_ids = {
        product.pk for category in visible_categories for product in category.available_products
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
    for category in visible_categories:
        for product in category.available_products:
            product.has_customization = product.pk in customizable_ids
    for group in daily_groups:
        for product in group["products"]:
            product.has_customization = product.pk in customizable_ids

    from orders.cart import cart_control_summary
    cart_controls = cart_control_summary(request.session)

    return render(request, "menu/public_menu.html", {
        "categories": visible_categories,
        "daily_menu": daily_menu,
        "daily_groups": daily_groups,
        "active_periods": active_periods,
        "meal_packages": MealPackage.objects.filter(is_active=True),
        "advance_food_order": current_time < time(13, 0),
        "public_menu_mode_label": "Desayunos" if public_mode == "breakfast" else "Comida",
        "product_customizations": product_customizations,
        "cart_controls": cart_controls,
    })
