from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import SECTION_ROLE_MATRIX, role_required

from .forms import CategoryForm, DailyMenuForm, ProductForm
from .models import Category, DailyMenu, Product, ServicePeriod


@role_required(*SECTION_ROLE_MATRIX["menu"])
def configuration(request):
    categories = Category.objects.annotate(product_count=Count("products"))
    products = Product.objects.select_related("category").prefetch_related("service_periods")
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
def category_create(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        messages.success(request, f"La categoría {category.name} fue creada.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {"form": form, "title": "Nueva categoría"})


@role_required(*SECTION_ROLE_MATRIX["menu"])
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La categoría fue actualizada.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {"form": form, "title": f"Editar categoría: {category.name}"})


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
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"El producto {product.name} fue creado.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {"form": form, "title": "Nuevo producto"})


@role_required(*SECTION_ROLE_MATRIX["menu"])
def product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El producto fue actualizado.")
        return redirect("menu:configuration")
    return render(request, "menu/form.html", {"form": form, "title": f"Editar producto: {product.name}"})


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


def public_menu(request):
    current_time = timezone.localtime().time()
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
    categories = Category.objects.prefetch_related(
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

    return render(request, "menu/public_menu.html", {
        "categories": visible_categories,
        "daily_menu": daily_menu,
        "daily_groups": daily_groups,
        "active_periods": active_periods,
    })
