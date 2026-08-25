# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas vistas implementan CRUD (crear, leer, actualizar y eliminar). Las internas exigen
# Administrador en backend. `public_menu` es anónima y filtra no disponibles. Borra esta nota.

from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.roles import SECTION_ROLE_MATRIX, role_required

from .forms import CategoryForm, ProductForm
from .models import Category, Product


@role_required(*SECTION_ROLE_MATRIX["menu"])
def configuration(request):
    categories = Category.objects.annotate(product_count=Count("products"))
    products = Product.objects.select_related("category")
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


def public_menu(request):
    available_products = Product.objects.filter(is_available=True).order_by("sort_order", "name")
    categories = Category.objects.prefetch_related(
        Prefetch("products", queryset=available_products, to_attr="available_products")
    )
    visible_categories = [category for category in categories if category.available_products]
    return render(request, "menu/public_menu.html", {"categories": visible_categories})
