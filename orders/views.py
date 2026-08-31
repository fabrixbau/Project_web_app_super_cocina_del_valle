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
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, SECTION_ROLE_MATRIX, role_required, user_has_any_role
from menu.models import DailyMenu, MealPackage, Product
from menu.selection import resolve_product_selection

from .cart import add_package, add_product, cart_control_summary, clear, decrease_product, get_order_mode, product_is_orderable, remove_item, resolve_cart, set_order_mode, update_item
from .forms import PackageCartForm, ProductCartForm, PublicCheckoutForm, PublicOrderModeForm
from .models import Order
from .services import ACTION_LABELS, assign_delivery, available_order_actions, create_public_cart_order, transition_order


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
        messages.error(request, error.message)
    else:
        messages.success(request, f"El pedido ahora está: {order.get_status_display()}.")
    return redirect("orders:order_detail", order_id=order.pk)


@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def delivery_board(request):
    delivery_orders = Order.objects.filter(
        order_type=Order.OrderType.DELIVERY,
    ).select_related("delivery_person", "delivery_assigned_by")
    repartidores = get_user_model().objects.filter(
        is_active=True, groups__name=DELIVERY,
    ).distinct().order_by("first_name", "username")
    return render(request, "orders/delivery_board.html", {
        "unassigned_orders": delivery_orders.filter(delivery_person__isnull=True),
        "assigned_orders": delivery_orders.filter(delivery_person__isnull=False),
        "repartidores": repartidores,
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
        messages.error(request, error.message)
    else:
        messages.success(request, f"El repartidor de {order.formatted_number} fue actualizado.")
    return redirect("deliveries:delivery_board")


@require_POST
@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def delivery_complete(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = transition_order(order=order, action="complete_delivery", actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"{order.formatted_number} quedó registrado como entregado.")
    return redirect("deliveries:delivery_board")
