# NOTA TEMPORAL PARA APRENDIZAJE:
# El flujo público ahora agrega paquetes/productos a sesión y crea la orden únicamente
# desde checkout. El panel interno conserva listado, detalle y resolución. Borra esta nota.
# Borra esta nota.

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, ORDER_TAKER, SECTION_ROLE_MATRIX, role_required, user_has_any_role
from menu.models import DailyMenu, MealPackage, Product

from .cart import add_package, add_product, clear, product_is_orderable, remove_item, resolve_cart, update_item
from .forms import PackageCartForm, ProductCartForm, PublicCheckoutForm
from .models import Order
from .services import create_public_cart_order, resolve_pending_order


def public_package_order(request, package_type):
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
    })


@require_POST
def public_product_add(request, product_id):
    product = get_object_or_404(Product.objects.prefetch_related("service_periods"), pk=product_id)
    form = ProductCartForm(request.POST)
    if not product_is_orderable(product):
        messages.error(request, "Ese producto no está disponible para pedir ahora.")
    elif form.is_valid():
        add_product(request.session, product=product, quantity=form.cleaned_data["quantity"])
        messages.success(request, f"{product.name} fue agregado al carrito.")
        return redirect("public_portal:cart")
    else:
        messages.error(request, "La cantidad solicitada no es válida.")
    return redirect("public_portal:menu")


def public_cart(request):
    return render(request, "orders/public_cart.html", {"cart": resolve_cart(request.session)})


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
    cart_data = resolve_cart(request.session)
    if not cart_data["items"]:
        messages.error(request, "Agrega al menos un producto antes de finalizar.")
        return redirect("public_portal:cart")
    form = PublicCheckoutForm(request.POST or None, cart_total=cart_data["total"])
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
    return render(request, "orders/public_checkout.html", {"cart": cart_data, "form": form})


def public_order_confirmation(request, public_token):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), public_token=public_token,
        source=Order.Source.PUBLIC_WEB,
    )
    return render(request, "orders/public_order_confirmation.html", {"order": order})


@role_required(*SECTION_ROLE_MATRIX["orders"])
def order_list(request):
    orders = Order.objects.prefetch_related("items")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    order_type = request.GET.get("order_type", "").strip()
    if search:
        number_query = Q()
        if search.lstrip("#").isdigit():
            number_query = Q(daily_number=int(search.lstrip("#")))
        orders = orders.filter(
            number_query | Q(customer_name__icontains=search) | Q(phone__icontains=search)
        )
    if status in Order.Status.values:
        orders = orders.filter(status=status)
    if order_type in Order.OrderType.values:
        orders = orders.filter(order_type=order_type)
    return render(request, "orders/order_list.html", {
        "orders": orders,
        "status_choices": Order.Status.choices,
        "order_type_choices": Order.OrderType.choices,
        "search": search,
        "selected_status": status,
        "selected_order_type": order_type,
    })


@role_required(*SECTION_ROLE_MATRIX["orders"])
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=order_id)
    can_resolve = user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    return render(request, "orders/order_detail.html", {
        "order": order,
        "can_resolve": can_resolve,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def order_resolve(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = resolve_pending_order(
            order=order, action=request.POST.get("action"), actor=request.user
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "El pedido fue confirmado." if order.status == Order.Status.CONFIRMED else "El pedido fue cancelado.")
    return redirect("orders:order_detail", order_id=order.pk)
