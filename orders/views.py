# NOTA TEMPORAL PARA APRENDIZAJE:
# Las vistas finales forman el panel operativo y las acciones seguras de reparto.
# El flujo público exige modalidad en sesión antes del menú; checkout usa esa decisión
# para mostrar solo los datos necesarios. Borra esta nota después de leerla.
# Corrida y ejecutiva permiten pedidos anticipados antes de la 1 p. m. con un aviso.
# Productos generales también respetan la visibilidad pública de su categoría según horario.

import copy
import csv
import re
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Case, DateTimeField, Exists, F, IntegerField, OuterRef, Prefetch, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from urllib.parse import urlencode
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER, SECTION_ROLE_MATRIX, role_required, user_has_any_role
from config.printing import order_print_context, printable_item, selected_printable_items
from print_station.views import queue_ticket
from menu.inventory import filter_products_by_stock, stock_warning_payload
from menu.egg import egg_products, selected_egg
from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product
from menu.packaging import parse_packaging_quantities
from menu.selection import apply_package_component_customizations, expanded_customizations, requested_customizations, requested_packages, resolve_product_selection, serialize_product_selector, ticket_item_name, ticket_modifications
from tables.models import DiningTable, TableAccount

from public_portal.preview import public_time
from .delivery_zone import street_choices
from .cart import add_package, add_product, cart_control_summary, cart_has_lunch_items, clear, decrease_product, get_order_mode, product_is_orderable, remove_item, resolve_cart, set_cart_note, set_item_note, update_item, update_product_selection
from .coffee_report import coffee_sales_for_date
from .phones import phone_key as normalize_customer_phone
from .forms import CustomerAddressForm, CustomerForm, DeliveryTipForm, InternalOrderAutosaveForm, InternalOrderForm, InternalPackageExtrasForm, InternalPackageForm, PackageCartForm, ProductCartForm, PublicCheckoutForm
from .models import CashRegisterCut, CashRegisterExpense, CoffeeSettlement, Customer, CustomerAddress, CustomerCreditMovement, CustomerDebt, CustomerDebtMovement, Order, OrderItem, TerminalCut, TerminalMovement
from .services import ACTION_LABELS, customer_with_phone, duplicate_customer_groups, merge_customers, link_public_order_customer, add_cash_register_expense, add_customer_credit, apply_credit_to_debts, open_customer_debts, suggested_credit_allocation, add_internal_auto_meal_component, add_internal_order_package, add_internal_order_product, add_water_to_internal_package, assign_delivery, autosave_internal_order_customer, available_order_actions, can_update_order_payment, change_internal_order_item, change_internal_order_type, close_internal_order_capture, confirm_cash_settlement, create_customer_debt, create_public_cart_order, refund_customer_credit, register_customer_debt_payment, save_internal_order, set_cashier_release, set_customer_debt_forgiven, settle_selected_debts_from_cashier, start_internal_order, transfer_order_to_table, transition_order, update_cash_register_cut, update_cashier_payment, update_delivery_tip, update_internal_order_item_note, update_internal_order_note, update_internal_package_extras


INTERNAL_MENU_MODE_KEY = "internal_order_menu_mode"
INTERNAL_AUTO_MEAL_SESSION_KEY = "internal_order_auto_meal_builders"

# NOTA TEMPORAL PARA APRENDIZAJE: PaymentMethod.CREDIT ("Saldo a favor") sólo lo
# asigna el sistema (cuando el saldo a favor cubre el pedido por completo al
# cerrar la captura, en close_internal_order_capture) — nunca es una opción que
# Caja o Pedidos elijan a mano, porque no representa dinero que alguien recibió.
# Por eso se excluye de cualquier <select>/botón donde el operador pueda ASIGNAR
# la forma de pago (depósito, abono, cambiar método de un pedido); sí puede
# aparecer en filtros de sólo lectura (Caja ya lo permite). Borra esta nota.
ASSIGNABLE_PAYMENT_METHOD_CHOICES = [
    choice for choice in Order.PaymentMethod.choices if choice[0] != Order.PaymentMethod.CREDIT
]


def _order_locked_for_edit(order, user):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta regla se consulta tanto al dibujar el
    # editor como en cada POST. Ocultar controles mejora la interfaz; validar aquí
    # impide saltarse el bloqueo fabricando una petición. Borra esta nota al leerla.
    return (
        order.status in {Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED}
        and not user_has_any_role(user, (ADMIN,))
    )


def _locked_order_response(request, order):
    message = "El pedido ya está en reparto y sólo un administrador puede modificar sus datos."
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "error": message}, status=403)
    messages.error(request, message)
    return redirect("orders:order_detail", order_id=order.pk)


def _order_actions_for_user(order, user):
    actions = list(available_order_actions(order))
    if user_has_any_role(user, (ADMIN,)):
        if order.status not in {
            Order.Status.CANCELED, Order.Status.PICKED_UP, Order.Status.DELIVERED,
        } and "cancel" not in actions:
            actions.append("cancel")
        return actions
    if not user_has_any_role(user, (ORDER_TAKER,)):
        return []
    # Telefonista puede cerrar una entrega ya despachada, pero nunca reiniciar un
    # ciclo finalizado. Cualquier otra edición permanece bloqueada por separado.
    if order.status == Order.Status.OUT_FOR_DELIVERY:
        return [action for action in actions if action == "complete_delivery"]
    return [action for action in actions if action != "restart_cycle"]


def _can_edit_delivery_tip(order, user):
    # NOTA TEMPORAL PARA APRENDIZAJE: la propina es la única excepción al bloqueo
    # de En reparto. El repartidor debe ser el asignado y pierde el permiso al quedar
    # Entregado; el resto del pedido continúa siempre en sólo lectura. Borra esta nota.
    if user_has_any_role(user, (ADMIN,)):
        return True
    is_delivery_profile = (
        user_has_any_role(user, (DELIVERY,))
        and not user_has_any_role(user, (ADMIN, ORDER_TAKER))
    )
    if is_delivery_profile:
        return (
            order.status == Order.Status.OUT_FOR_DELIVERY
            and order.delivery_person_id == user.pk
            and order.payment_method in {Order.PaymentMethod.CASH, Order.PaymentMethod.CARD}
            and order.delivery_tip_updated_at is None
        )
    if user_has_any_role(user, (ORDER_TAKER,)):
        return (
            not _order_locked_for_edit(order, user)
            and order.payment_method != Order.PaymentMethod.CARD
        )
    return False


def _can_edit_delivery_tip_on_board(order, user):
    # NOTA TEMPORAL PARA APRENDIZAJE: en Repartos, sólo Administrador puede corregir
    # libremente la propina; Telefonista pierde esa edición aquí aunque la conserve
    # durante la captura interna. El Repartidor asignado sigue capturando la suya una
    # sola vez, igual que antes — pero ahora la ventana depende del método de pago:
    # Efectivo sigue exigiendo que el pedido siga "En reparto" (se resuelve con
    # "Cambio devuelto" en Caja, que ya lo pasa a Entregado); Terminal ahora también
    # se puede registrar con el pedido ya en "Entregado", porque el propio Repartidor
    # es quien marca esa transición (ver delivery_complete) y necesita poder anotar la
    # propina en ese mismo momento. Si el ciclo se reinicia, `delivery_tip_updated_at`
    # queda con la fecha del ciclo anterior y el Repartidor pierde la oportunidad —
    # a propósito, sólo Admin puede tocarla después de eso. Borra esta nota al leerla.
    if user_has_any_role(user, (ADMIN,)):
        return True
    is_delivery_profile = (
        user_has_any_role(user, (DELIVERY,))
        and not user_has_any_role(user, (ADMIN, ORDER_TAKER))
    )
    if not is_delivery_profile:
        return False
    if order.delivery_person_id != user.pk or order.delivery_tip_updated_at is not None:
        return False
    if order.payment_method == Order.PaymentMethod.CASH:
        return order.status == Order.Status.OUT_FOR_DELIVERY
    if order.payment_method == Order.PaymentMethod.CARD:
        return order.status in {Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED}
    return False


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
    # NOTA TEMPORAL PARA APRENDIZAJE: espejo de planned_auto_meal_selection en
    # tables/views.py — antes sólo existía una comida "en construcción" a la vez y se
    # rechazaba capturar el mismo tiempo dos veces seguidas, obligando a completar una
    # comida antes de iniciar otra. Ahora se busca, entre todas las comidas pendientes
    # de este pedido, la primera a la que le falte este tiempo (o se abre una nueva si
    # todas ya lo tienen), permitiendo capturar varios tiempos iguales seguidos sin
    # importar el orden. Borra esta nota después de leerla.
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


def _customer_credit_projection(order):
    # NOTA TEMPORAL PARA APRENDIZAJE: proyección informativa, en vivo, de lo que
    # pasaría con el saldo a favor del cliente SI el pedido se cerrara ahora mismo
    # con el total actual — no aplica ni descuenta nada todavía (eso sigue pasando
    # sólo al cerrar la captura, en apply_customer_credit_to_order). Se usa tanto
    # en la carga inicial de la página como en cada respuesta AJAX que ya devuelve
    # el ticket (internal_order_ticket), para que el aviso se mantenga al día sin
    # recargar. Borra esta nota después de leerla.
    if not order.agenda_customer_id:
        return None
    balance = order.agenda_customer.credit_balance
    if balance <= 0:
        return None
    return {
        "balance": f"{balance:.2f}",
        "applied": f"{min(balance, order.total):.2f}",
        "remaining_balance": f"{max(balance - order.total, Decimal('0')):.2f}",
        "remaining_after_credit": f"{max(order.total - balance, Decimal('0')):.2f}",
    }


def _order_debt_badge(order):
    # NOTA TEMPORAL PARA APRENDIZAJE: a diferencia del saldo a favor (que vive en
    # Customer.credit_balance, un solo número cacheado), el adeudo se guarda como un
    # CustomerDebt por pedido — así que "cuánto debe este cliente en total" es la
    # suma de todos sus adeudos todavía abiertos (pendiente o parcial), sin importar
    # a qué otro pedido pertenezca cada uno. Se usa en los tableros (Pedidos, Caja,
    # Repartos) para avisar de un vistazo si vale la pena cobrar ese adeudo también.
    # Borra esta nota después de leerla.
    if not order.agenda_customer_id:
        return None
    open_debts = [
        debt for debt in order.agenda_customer.debts.all()
        if debt.status in (CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL)
    ]
    if not open_debts:
        return None
    open_debts.sort(key=lambda debt: debt.created_at)
    return {
        "balance": sum((debt.balance for debt in open_debts), Decimal("0")),
        "count": len(open_debts),
        "debts": open_debts,
    }


def _customer_debt_projection(order):
    # NOTA TEMPORAL PARA APRENDIZAJE: espejo de _customer_credit_projection, pero
    # para "saldo en contra" — informativo, en vivo, durante la captura de un pedido
    # NUEVO. No decide nada sobre cómo se van a cobrar los adeudos viejos (eso pasa
    # en Caja, al registrar el pago); aquí sólo mostramos cuánto debe ya el cliente,
    # en qué pedidos, y cuánto deberá en total si este pedido nuevo también quedara
    # sin pagar. A diferencia de _order_debt_badge (que usa agenda_customer.debts.all()
    # ya prefetcheado en los tableros), esta función se llama una sola vez por
    # respuesta del ticket, así que puede consultar directo sin prefetch previo.
    # Borra esta nota después de leerla.
    if not order.agenda_customer_id:
        return None
    open_debts = list(order.agenda_customer.debts.select_related("order").filter(
        status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL),
    ))
    if not open_debts:
        return None
    balance = sum((debt.balance for debt in open_debts), Decimal("0"))
    return {
        "balance": f"{balance:.2f}",
        "count": len(open_debts),
        "projected_total": f"{balance + order.total:.2f}",
        "orders": [{
            "id": debt.order_id, "number": debt.order.formatted_number,
            "balance": f"{debt.balance:.2f}",
            "url": reverse("orders:internal_order_edit", args=(debt.order_id,)),
        } for debt in open_debts],
    }


def internal_order_ticket(order):
    items = []
    quantities = {}
    candidate_quantities = {}
    meal_quantities = {}
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
            if item.bread:
                description_parts.append("Con bolillo")
            if item.beans:
                description_parts.append("Con frijoles")
            if item.egg_name_snapshot:
                description_parts.append(f"Con {item.egg_name_snapshot}")
        is_package = item.item_type == OrderItem.ItemType.PACKAGE
        items.append({
            "id": item.pk,
            "name": ticket_item_name(base_name, item, is_package=is_package),
            # Cómo quedó modificado: ingredientes del producto o tiempos del paquete.
            "modifications": ticket_modifications(item, is_package=is_package),
            "quantity": item.quantity, "subtotal": f"{item.subtotal:.2f}",
            "is_customized": item.is_customized,
            "is_package_candidate": item.is_package_candidate,
            "description": "" if item.is_package_candidate else " · ".join(filter(None, description_parts)),
            "is_package": item.item_type == OrderItem.ItemType.PACKAGE,
            "with_water": item.with_water, "tortillas": item.tortillas, "bread": item.bread,
            "egg_product_id": item.egg_product_id,
            "beans": item.beans, "comment": item.customization_comment,
            "edit_extras_url": reverse("orders:internal_order_package_extras", args=(order.pk, item.pk)) if item.item_type == OrderItem.ItemType.PACKAGE else "",
            "edit_note_url": reverse("orders:internal_order_item_note", args=(order.pk, item.pk)),
            "change_url": reverse("orders:internal_order_item_change", args=(order.pk, item.pk)),
        })
        if item.item_type == OrderItem.ItemType.PRODUCT:
            target = candidate_quantities if item.is_package_candidate else quantities
            target[str(item.product_id)] = target.get(str(item.product_id), 0) + item.quantity
            if item.is_package_candidate:
                meal_quantities[str(item.product_id)] = meal_quantities.get(str(item.product_id), 0) + item.quantity
        else:
            # Las piezas que ya forman un paquete siguen contando en las tarjetas de
            # Comida corrida/ejecutiva (antes el contador volvía a 0 al armarse).
            for course_id in (item.first_course_id, item.second_course_id, item.main_course_id):
                if course_id:
                    meal_quantities[str(course_id)] = meal_quantities.get(str(course_id), 0) + item.quantity
    return {
        "items": items, "total": f"{order.total:.2f}",
        "count": sum(item["quantity"] for item in items), "quantities": quantities,
        "candidate_quantities": candidate_quantities, "meal_quantities": meal_quantities, "note": order.notes,
        "customer_credit": _customer_credit_projection(order),
        "customer_debt": _customer_debt_projection(order),
        "stock_warnings": stock_warning_payload(selected_date=order.operating_date),
    }


def public_package_order(request, package_type):
    if not get_order_mode(request.session):
        return redirect("public_portal:home")
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
    form = PackageCartForm(request.POST or None, package=package, daily_menu=daily_menu, customers_only=True)
    if request.method == "POST":
        # Con el contador − # + llegan varias comidas en `package_batch` (mismo formato que
        # el diálogo del personal). Se validan todas antes de agregar cualquiera.
        try:
            requested = requested_packages(request.POST)
        except ValidationError as error:
            form.add_error(None, error.message)
            requested = []
        candidates = [
            (PackageCartForm(data, package=package, daily_menu=daily_menu, customers_only=True), quantity)
            for data, quantity in requested
        ]
        invalid = next((candidate for candidate, _quantity in candidates if not candidate.is_valid()), None)
        if candidates and not invalid:
            total_meals = 0
            for candidate, quantity in candidates:
                cleaned = {**candidate.cleaned_data, "quantity": min(99, candidate.cleaned_data["quantity"] * quantity)}
                add_package(request.session, package=package, daily_menu=daily_menu, cleaned_data=cleaned)
                total_meals += cleaned["quantity"]
            messages.success(
                request,
                "La comida fue agregada al pedido." if total_meals == 1 else f"Se agregaron {total_meals} comidas al pedido.",
            )
            # Dos botones: "Agregar y seguir pidiendo" (menú) o "Agregar e ir a pagar" (finalizar).
            return redirect("public_portal:checkout" if request.POST.get("next") == "checkout" else "public_portal:menu")
        if invalid:
            form = invalid
    return render(request, "orders/public_package_order.html", {
        "package": package, "daily_menu": daily_menu, "form": form,
        "advance_food_order": public_time(request.session) < time(13, 0),
    })


@require_POST
def public_product_add(request, product_id):
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if not get_order_mode(request.session):
        if wants_json:
            return JsonResponse({"ok": False, "error": "Primero selecciona la modalidad del pedido."}, status=400)
        return redirect("public_portal:home")
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
    current_time = public_time(request.session)
    visibility_field = "show_on_public_breakfast" if current_time < time(12, 31) else "show_on_public_lunch"
    category_is_visible = product.component_type in daily_component_types or getattr(product.category, visibility_field)
    if current_time < time(12, 31) and product.category.show_on_public_lunch:
        category_is_visible = True
    if product.packaging_kind != Product.PackagingKind.NONE:
        error_message = "Los envases se registran directamente por el personal."
    elif not category_is_visible:
        error_message = "Ese producto no está visible en el menú de este horario."
    elif not product_is_orderable(product, now=current_time):
        error_message = "Ese producto no está disponible para pedir ahora."
    elif form.is_valid():
        try:
            # Se validan todas las configuraciones antes de tocar el carrito.
            batch = request.POST.get("customization_batch")
            selections = [
                (resolve_product_selection(product, raw_option_ids, raw_comment),
                 quantity if batch else form.cleaned_data["quantity"])
                for raw_option_ids, raw_comment, quantity in requested_customizations(request.POST)
            ]
        except ValidationError as error:
            error_message = error.message
        else:
            for selection, quantity in selections:
                add_product(request.session, product=product, quantity=quantity, selection=selection)
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
        return redirect("public_portal:home")
    return render(request, "orders/public_cart.html", {
        "cart": resolve_cart(request.session), "order_type": order_type,
        "order_type_label": dict(Order.OrderType.choices)[order_type],
    })


@require_POST
def public_cart_update(request, key):
    form = ProductCartForm(request.POST)
    updated = form.is_valid() and update_item(request.session, key=key, quantity=form.cleaned_data["quantity"])
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Los botones del ticket no recargan la página: un aviso guardado aquí se
        # acumularía y aparecería de golpe en la siguiente pantalla (p. ej. al Armar).
        return JsonResponse({
            "ok": bool(updated), "cart": cart_control_summary(request.session),
            "error": "No fue posible actualizar esa partida." if not updated else "",
        }, status=200 if updated else 400)
    if updated:
        messages.success(request, "La cantidad fue actualizada.")
    else:
        messages.error(request, "No fue posible actualizar esa partida.")
    return redirect("public_portal:cart")


@require_POST
def public_cart_remove(request, key):
    removed = remove_item(request.session, key=key)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": bool(removed), "cart": cart_control_summary(request.session),
            "error": "La partida ya no está en tu ticket." if not removed else "",
        }, status=200 if removed else 404)
    if removed:
        messages.success(request, "La partida fue eliminada.")
    return redirect("public_portal:cart")


@require_POST
def public_cart_note(request):
    set_cart_note(request.session, request.POST.get("note", ""))
    return JsonResponse({"ok": True, "cart": cart_control_summary(request.session)})


@require_POST
def public_cart_customize(request, key, product_id):
    product = get_object_or_404(Product.objects.prefetch_related("option_groups__options"), pk=product_id)
    try:
        selection = resolve_product_selection(
            product, request.POST.getlist("option_ids"), request.POST.get("customization_comment", ""),
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    if not update_product_selection(request.session, key=key, product=product, selection=selection):
        return JsonResponse({"ok": False, "error": "La partida ya no está en tu ticket."}, status=404)
    return JsonResponse({"ok": True, "cart": cart_control_summary(request.session)})


@require_POST
def public_cart_item_note(request, key):
    if not set_item_note(request.session, key=key, note=request.POST.get("note", "")):
        return JsonResponse({"ok": False, "error": "La partida ya no está en tu ticket."}, status=404)
    return JsonResponse({"ok": True, "cart": cart_control_summary(request.session)})


def public_checkout(request):
    order_type = get_order_mode(request.session)
    if not order_type:
        return redirect("public_portal:home")
    cart_data = resolve_cart(request.session)
    if not cart_data["items"]:
        messages.error(request, "Agrega al menos un producto antes de finalizar.")
        return redirect("public_portal:cart")
    # Si un envío anterior se rechazó por el código de seguridad, se recuperan sus datos.
    draft = request.session.pop("public_checkout_draft", None) if request.method == "GET" else None
    form = PublicCheckoutForm(
        request.POST or None, cart_total=cart_data["total"], order_type=order_type,
        initial={"notes": request.session.get("public_order_note", ""), **(draft or {})},
        now=public_time(request.session),
        earliest=time(13, 0) if cart_has_lunch_items(cart_data) else None,
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
        "summary": cart_control_summary(request.session),
        "delivery_streets": street_choices() if order_type == Order.OrderType.DELIVERY else [],
    })


def public_order_confirmation(request, public_token):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), public_token=public_token,
        source=Order.Source.PUBLIC_WEB,
    )
    return render(request, "orders/public_order_confirmation.html", {"order": order})


def _pending_notification():
    """Pedido web cuya notificación nadie ha abierto desde Notificaciones ("Atender y abrir").

    En Pedidos y Caja esos pedidos abren la pantalla del pedido (no el editor) y llevan la
    marca "Sin atender"; la notificación sólo se apaga al abrirla desde Notificaciones.
    """
    from notifications.models import InternalNotification

    return Exists(InternalNotification.objects.filter(order=OuterRef("pk"), is_read=False))


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


def _full_folio_search_query(search):
    """Return the exact visible-folio query, or None for ordinary search text."""
    digits = search.strip().lstrip("#")
    # El folio visible siempre contiene DDMM y un consecutivo de al menos tres
    # posiciones. Un consecutivo corto sigue siendo una búsqueda normal.
    if len(digits) < 7 or not digits.isdigit():
        return None
    return Q(
        operating_date__day=int(digits[:2]),
        operating_date__month=int(digits[2:4]),
        daily_number=int(digits[4:]),
    )


def _operational_board_ordering(queryset):
    """Normales por creación; programados al final por hora solicitada."""
    scheduled_condition = Q(requested_for__gte=F("created_at") + timedelta(hours=1))
    return queryset.annotate(
        _scheduled_group=Case(
            When(scheduled_condition, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        _scheduled_time=Case(
            When(scheduled_condition, then=F("requested_for")),
            default=Value(None),
            output_field=DateTimeField(),
        ),
    ).order_by("_scheduled_group", "_scheduled_time", "created_at", "id")


def _board_order_search_options(date_from, date_to):
    return [
        {"folio": order.formatted_number, "customer": order.customer_name or "Sin nombre"}
        for order in Order.objects.filter(
            operating_date__range=(date_from, date_to),
        ).only("daily_number", "operating_date", "customer_name").order_by(
            "-operating_date", "-daily_number",
        )
    ]


@role_required(*SECTION_ROLE_MATRIX["orders"])
def order_list(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: select_related trae al repartidor en la misma
    # consulta que cada pedido. Así podemos mostrarlo en el listado sin hacer una
    # consulta adicional por cada fila. Borra esta nota después de leerla.
    orders = Order.objects.select_related(
        "delivery_person", "agenda_customer", "customer_debt",
    ).prefetch_related("items", "agenda_customer__debts").annotate(has_pending_notification=_pending_notification())
    today = timezone.localdate()
    date_from = _report_date(request.GET.get("date_from"), today)
    date_to = _report_date(request.GET.get("date_to"), today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    search = request.GET.get("q", "").strip()
    exact_folio_query = _full_folio_search_query(search)
    if exact_folio_query is not None:
        orders = orders.filter(exact_folio_query)
    else:
        orders = orders.filter(operating_date__range=(date_from, date_to))
    status = request.GET.get("status", "").strip()
    order_type = request.GET.get("order_type", "").strip()
    scope = request.GET.get("scope", "active").strip()
    # NOTA TEMPORAL PARA APRENDIZAJE: el alcance separa la bandeja operativa del
    # historial terminado. El filtro Estado continúa funcionando dentro del alcance
    # elegido, por lo que también puede afinarse a sólo Entregado o sólo Recogido.
    # Borra esta nota después de leerla.
    final_statuses = (Order.Status.DELIVERED, Order.Status.PICKED_UP)
    inactive_statuses = (*final_statuses, Order.Status.CANCELED, Order.Status.TRANSFERRED)
    if exact_folio_query is not None:
        scope = "all"
        status = ""
        order_type = ""
    else:
        if scope == "completed":
            orders = orders.filter(status__in=final_statuses)
        elif scope == "all":
            pass
        else:
            scope = "active"
            orders = orders.exclude(status__in=inactive_statuses)
    if search and exact_folio_query is None:
        number_query = _folio_search_query(search)
        orders = orders.filter(
            number_query | Q(customer_name__icontains=search) | Q(phone__icontains=search)
        )
    if exact_folio_query is None and status in Order.Status.values:
        orders = orders.filter(status=status)
    if exact_folio_query is None and order_type in Order.OrderType.values:
        orders = orders.filter(order_type=order_type)
    orders = list(_operational_board_ordering(orders))
    # NOTA TEMPORAL PARA APRENDIZAJE: este aviso es independiente del filtro de fecha
    # de arriba (que puede estar mostrando otro día) — siempre revisa el día de hoy,
    # para que un administrador sepa de un vistazo si quedó algo por cerrar sin tener
    # que cambiar su filtro. Sólo se calcula para Administrador. Borra esta nota.
    pending_today = None
    if user_has_any_role(request.user, (ADMIN,)):
        pending_today = list(
            Order.objects.filter(operating_date=today).exclude(status__in=inactive_statuses)
            .order_by("daily_number")
        )
    # NOTA TEMPORAL PARA APRENDIZAJE: "Pasar a mesa" vive aquí (el tablero de
    # Pedidos) porque Mesero puede consultarlo pero no tiene acceso a la pantalla
    # completa de captura (internal_order_edit es sólo Administrador/Telefonista)
    # — necesita poder transferir el pedido sin abrirlo. Sólo Administrador y
    # Mesero pueden hacerlo, según pidió el desarrollador. Borra esta nota.
    can_transfer_order_to_table = user_has_any_role(request.user, (ADMIN, WAITER))
    available_tables = DiningTable.objects.filter(is_active=True).exclude(
        accounts__status=TableAccount.Status.OPEN,
    ).order_by("display_order", "name") if can_transfer_order_to_table else DiningTable.objects.none()
    waiters_for_transfer = get_user_model().objects.filter(
        is_active=True, groups__name=WAITER,
    ).distinct().order_by("first_name", "username") if user_has_any_role(request.user, (ADMIN,)) else get_user_model().objects.none()
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
        order.has_no_products = not items
        actions = [action for action in _order_actions_for_user(order, request.user) if action != "cancel"]
        if order.has_no_products or any(item.is_package_candidate for item in items):
            actions = [action for action in actions if action != "mark_ready"]
        order.quick_action = actions[0] if actions else ""
        order.quick_action_label = ACTION_LABELS.get(order.quick_action, "")
        order.can_cancel = (
            user_has_any_role(request.user, (ADMIN,))
            and order.status not in {Order.Status.CANCELED, Order.Status.PICKED_UP, Order.Status.DELIVERED}
        )
        order.can_mark_unpaid = (
            user_has_any_role(request.user, (ADMIN,))
            and order.status != Order.Status.CANCELED
            and not hasattr(order, "customer_debt")
        )
        order.can_edit_payment = can_update_order_payment(order=order, actor=request.user)
        order.customer_debt_note = _order_debt_badge(order)
        order.can_transfer_to_table = (
            can_transfer_order_to_table
            and order.order_type in {Order.OrderType.PICKUP, Order.OrderType.DELIVERY}
            and order.status not in {
                Order.Status.CANCELED, Order.Status.DELIVERED,
                Order.Status.PICKED_UP, Order.Status.TRANSFERRED,
            }
        )
    return render(request, "orders/order_list.html", {
        "orders": orders,
        "delivery_orders": [order for order in orders if order.order_type == Order.OrderType.DELIVERY],
        "pickup_orders": [order for order in orders if order.order_type == Order.OrderType.PICKUP],
        "can_transfer_order_to_table": can_transfer_order_to_table,
        "available_tables": available_tables,
        "waiters_for_transfer": waiters_for_transfer,
        "status_choices": Order.Status.choices,
        "order_type_choices": Order.OrderType.choices,
        "search": search,
        "selected_status": status,
        "selected_order_type": order_type,
        "selected_scope": scope,
        "date_from": date_from,
        "date_to": date_to,
        "order_search_options": _board_order_search_options(date_from, date_to),
        "pending_today": pending_today,
        "can_capture_internal": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
        "can_manage_debts": user_has_any_role(request.user, (ADMIN,)),
    })


@require_POST
@role_required(ADMIN, WAITER)
def order_transfer_to_table(request, order_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: botón "Pasar a mesa" del tablero de Pedidos —
    # el desarrollador confirmó que sólo Administrador y Mesero pueden usarlo.
    # Administrador elige a qué mesero se le asigna la mesa; Mesero se asigna a sí
    # mismo automático, igual que ya pasa al abrir una mesa normal. Borra esta nota.
    order = get_object_or_404(Order, pk=order_id)
    table = get_object_or_404(DiningTable, pk=request.POST.get("table_id"))
    assigned_waiter = None
    if user_has_any_role(request.user, (ADMIN,)):
        waiter_id = request.POST.get("assigned_waiter", "")
        if waiter_id:
            assigned_waiter = get_object_or_404(get_user_model(), pk=waiter_id)
    try:
        new_account = transfer_order_to_table(
            order=order, table=table, actor=request.user, assigned_waiter=assigned_waiter,
        )
    except ValidationError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
        return redirect("orders:order_list")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "account_id": new_account.pk,
            "redirect_url": reverse("tables:table_detail", args=(new_account.pk,)),
        })
    messages.success(request, f"{order.formatted_number} se pasó a {table.name}.")
    return redirect("tables:table_detail", account_id=new_account.pk)


def _internal_order_initial(order):
    cash_bill = str(int(order.cash_tendered)) if order.cash_tendered in (50, 100, 150, 200, 500) else ""
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
        "pays_exact": (
            order.payment_method == Order.PaymentMethod.CASH
            and order.cash_tendered is not None and not order.needs_change
        ),
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
    phone_query = normalize_customer_phone(query)
    customers = Customer.objects.prefetch_related(
        "addresses",
        Prefetch(
            "debts", queryset=CustomerDebt.objects.only("id", "customer_id"),
            to_attr="debt_records",
        ),
    )
    if query:
        phone_filter = Q(phone_key__icontains=phone_query) if phone_query else Q(pk__isnull=True)
        customers = customers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
            | phone_filter
            | Q(addresses__street__icontains=query)
            | Q(addresses__neighborhood__icontains=query)
        ).distinct()
    return render(request, "orders/customer_list.html", {
        "duplicate_group_count": len(duplicate_customer_groups()),
        "customers": customers, "query": query,
        "can_delete_customers": user_has_any_role(request.user, (ADMIN,)),
    })


@require_POST
@role_required(ADMIN)
def customer_delete(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    # NOTA TEMPORAL PARA APRENDIZAJE: comprobamos primero para ofrecer un mensaje
    # comprensible, pero también capturamos ProtectedError por si nace un adeudo entre
    # la comprobación y el DELETE. Borra esta nota después de leerla.
    if customer.debts.exists():
        messages.error(request, f"No se puede eliminar a {customer.name} porque tiene historial de adeudos.")
        return redirect("orders:customer_list")
    customer_name = customer.name
    try:
        customer.delete()
    except ProtectedError:
        messages.error(request, f"No se puede eliminar a {customer_name} porque tiene información financiera protegida.")
    else:
        messages.success(request, f"{customer_name} fue eliminado de la agenda.")
    return redirect("orders:customer_list")


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
    customer = get_object_or_404(
        Customer.objects.prefetch_related(
            "addresses", "debts__order", "debts__movements__registered_by",
            "credit_movements__order", "credit_movements__registered_by",
        ),
        pk=customer_id,
    )
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
        elif action == "credit_deposit" and user_has_any_role(request.user, (ADMIN,)):
            try:
                add_customer_credit(
                    customer=customer, amount=request.POST.get("amount", ""),
                    payment_method=request.POST.get("payment_method", ""), actor=request.user,
                    note=request.POST.get("note", ""),
                )
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "El depósito fue registrado.")
                if open_customer_debts(customer):
                    return redirect(credit_apply_url(customer.pk, reverse("orders:customer_edit", args=(customer.pk,))))
            return redirect("orders:customer_edit", customer_id=customer.pk)
        elif action == "credit_refund" and user_has_any_role(request.user, (ADMIN,)):
            try:
                refund_customer_credit(
                    customer=customer, amount=request.POST.get("amount", ""),
                    actor=request.user, note=request.POST.get("note", ""),
                )
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "La devolución fue registrada.")
            return redirect("orders:customer_edit", customer_id=customer.pk)
    address_forms = [(address, CustomerAddressForm(instance=address, prefix=f"address-{address.pk}")) for address in customer.addresses.all()]
    return render(request, "orders/customer_form.html", {
        "customer": customer, "form": form, "address_forms": address_forms,
        "new_address_form": CustomerAddressForm(prefix="new"),
        "customer_debts": customer.debts.all(),
        "customer_outstanding": sum(
            (debt.balance for debt in customer.debts.all() if debt.status in {CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL}),
            Decimal("0"),
        ),
        "customer_credit_movements": customer.credit_movements.all()[:20],
        "can_manage_credit": user_has_any_role(request.user, (ADMIN,)),
        "can_apply_credit": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
    })


@role_required(ADMIN, ORDER_TAKER)
def customer_lookup(request):
    query = request.GET.get("q", "").strip()
    phone_query = normalize_customer_phone(query)
    customers = Customer.objects.prefetch_related("addresses", "debts__order")
    total = 0
    if query:
        phone_filter = Q(phone_key__icontains=phone_query) if phone_query else Q(pk__isnull=True)
        customers = customers.filter(
            Q(name__icontains=query) | Q(phone__icontains=query)
            | phone_filter
            | Q(addresses__street__icontains=query)
        ).distinct()
        total = customers.count()
        customers = customers.order_by("name")[:10]
    else:
        customers = customers.none()
    customer_rows = []
    for customer in customers:
        open_debts = [debt for debt in customer.debts.all() if debt.status in {CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL}]
        customer_rows.append({
        "id": customer.pk, "name": customer.name, "phone": customer.phone,
        "notes": customer.notes,
        "edit_url": reverse("orders:customer_edit", args=(customer.pk,)),
        "outstanding_balance": f"{sum((debt.balance for debt in open_debts), Decimal('0')):.2f}",
        "open_debt_count": len(open_debts),
        "debt_url": f"{reverse('cashier:debt_board')}?customer={customer.pk}",
        "open_debts": [{
            "id": debt.order_id, "number": debt.order.formatted_number,
            "balance": f"{debt.balance:.2f}",
            "url": reverse("orders:internal_order_edit", args=(debt.order_id,)),
        } for debt in open_debts],
        "credit_balance": f"{customer.credit_balance:.2f}",
        "addresses": [{
            "id": address.pk, "street": address.street,
            "exterior_number": address.exterior_number,
            "interior_number": address.interior_number,
            "neighborhood": address.neighborhood,
            "references": address.references,
        } for address in customer.addresses.all()],
        })
    # `results`/`total` alimentan la lupa con sugerencias (live-search.js) de Clientes.
    results = [{
        "label": row["name"],
        "detail": " · ".join(filter(None, (row["phone"], row["addresses"][0]["street"] if row["addresses"] else ""))),
        "url": row["edit_url"],
    } for row in customer_rows]
    return JsonResponse({"customers": customer_rows, "results": results, "total": total})


@role_required(ADMIN, ORDER_TAKER)
def internal_order_edit(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    close_failed = False
    form = InternalOrderForm(
        request.POST or None,
        initial=_internal_order_initial(order), order_total=order.total,
        closing=request.method == "POST" and request.POST.get("action") == "close",
        available_credit=order.agenda_customer.credit_balance if order.agenda_customer_id else 0,
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
        "products", queryset=Product.objects.filter(
            is_available=True,
            is_sold_individually=True,
            packaging_kind=Product.PackagingKind.NONE,
        ).order_by("sort_order", "name"), to_attr="capture_products",
    )))
    categories = [category for category in categories if category.capture_products]
    packaging_products = list(Product.objects.filter(
        is_available=True,
        is_sold_individually=True,
    ).exclude(packaging_kind=Product.PackagingKind.NONE).order_by("sort_order", "name"))
    daily_menu = DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED).select_related(
        "water_product", "chicken_consomme", "variable_first_course", "second_course_one",
        "second_course_two", "chicken_stew", "beef_stew", "varied_stew", "beans_order",
    ).first()
    from menu.catalog import limit_cold_drinks_to_daily_water

    categories = limit_cold_drinks_to_daily_water(
        categories, daily_menu, "capture_products",
    )
    for category in categories:
        category.capture_products = filter_products_by_stock(
            category.capture_products, daily_menu=daily_menu,
            channel=DailyProductStock.Channel.ORDERS,
        )
    running_meal_products = []
    executive_meal_products = []
    daily_order_products = []
    daily_order_loose_products = []
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
    daily_order_loose_products = filter_products_by_stock(
        list(Product.objects.filter(
            category__name="Comida por orden",
            category__show_on_table_lunch=True,
            is_available=True,
            is_sold_individually=True,
            packaging_kind=Product.PackagingKind.NONE,
        ).order_by("sort_order", "name")),
        daily_menu=daily_menu,
        channel=DailyProductStock.Channel.ORDERS,
    )
    daily_product_ids = {product.pk for product in daily_order_products}
    daily_order_loose_products = [
        product for product in daily_order_loose_products
        if product.pk not in daily_product_ids
    ]
    products = {product.pk: product for category in categories for product in category.capture_products}
    products.update({product.pk: product for product in packaging_products})
    for product in running_meal_products + executive_meal_products + daily_order_products + daily_order_loose_products:
        products[product.pk] = product
    package_options = []
    if mode == "lunch" and daily_menu:
        # NOTA TEMPORAL PARA APRENDIZAJE: antes la plantilla sólo recibía radios y
        # por eso no podía conocer la imagen de cada producto. Ahora conservamos el
        # formulario para validar, pero también enviamos sus tres querysets para
        # dibujar tarjetas visuales con los mismos IDs. Borra esta nota al leerla.
        for package in MealPackage.objects.filter(is_active=True):
            package_form = InternalPackageForm(
                package=package, daily_menu=daily_menu,
                prefix=f"internal-package-{package.pk}",
            )
            package_options.append({
                "package": package, "form": package_form,
                "first_products": filter_products_by_stock(list(package_form.fields["first_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS),
                "second_products": filter_products_by_stock(list(package_form.fields["second_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS),
                "main_products": filter_products_by_stock(list(package_form.fields["main_course"].queryset), daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS),
            })
    # Los tiempos del diálogo de paquete también se personalizan con la ficha.
    for option in package_options:
        for key in ("first_products", "second_products", "main_products"):
            products.update({product.pk: product for product in option[key]})
    selector_records = Product.objects.filter(pk__in=products).prefetch_related("option_groups__options")
    selector_data = {str(product.pk): serialize_product_selector(product) for product in selector_records}
    current_customer_debts = []
    if order.agenda_customer_id:
        current_customer_debts = list(order.agenda_customer.debts.select_related("order").filter(
            status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL),
        ))
    egg_choices = list(egg_products())
    known_egg_ids = {egg.pk for egg in egg_choices}
    egg_choices.extend(Product.objects.filter(
        pk__in=order.items.exclude(egg_product_id=None).values_list("egg_product_id", flat=True),
    ).exclude(pk__in=known_egg_ids))
    return render(request, "orders/internal_order_form.html", {
        "form": form, "order": order, "categories": categories,
        "packaging_products": packaging_products,
        "menu_mode": mode, "next_menu_mode": "lunch" if mode == "breakfast" else "breakfast",
        "menu_mode_label": "Desayunos" if mode == "breakfast" else "Comida",
        "next_menu_mode_label": "Cambiar a comida" if mode == "breakfast" else "Cambiar a desayunos",
        "selector_data": selector_data, "ticket": internal_order_ticket(order),
        "daily_menu": daily_menu, "package_options": package_options,
        "egg_options": [{"id": egg.pk, "name": egg.name, "price": str(egg.price)} for egg in egg_choices],
        "running_meal_products": running_meal_products,
        "executive_meal_products": executive_meal_products,
        "daily_order_products": daily_order_products,
        "daily_order_loose_products": daily_order_loose_products,
        "customer_debt_summary": {
            "balance": sum((debt.balance for debt in current_customer_debts), Decimal("0")),
            "count": len(current_customer_debts),
            "url": f"{reverse('cashier:debt_board')}?customer={order.agenda_customer_id}",
            "projected_total": sum((debt.balance for debt in current_customer_debts), Decimal("0")) + order.total,
            "orders": [{
                "id": debt.order_id, "number": debt.order.formatted_number,
                "balance": debt.balance,
                "url": reverse("orders:internal_order_edit", args=(debt.order_id,)),
            } for debt in current_customer_debts],
        } if current_customer_debts else None,
        # NOTA TEMPORAL PARA APRENDIZAJE: sólo informativo durante la captura — el
        # saldo todavía no se descuenta aquí (eso pasa hasta cerrar la captura, en
        # apply_customer_credit_to_order, porque el total puede seguir cambiando).
        # Borra esta nota después de leerla.
        "customer_credit_summary": {
            "balance": order.agenda_customer.credit_balance,
            "applied": min(order.agenda_customer.credit_balance, order.total),
            "remaining_balance": max(order.agenda_customer.credit_balance - order.total, Decimal("0")),
            "remaining_after_credit": max(order.total - order.agenda_customer.credit_balance, Decimal("0")),
        } if order.agenda_customer_id and order.agenda_customer.credit_balance > 0 else None,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_mode_switch(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    mode = request.POST.get("mode")
    if mode in {"breakfast", "lunch"}:
        request.session[INTERNAL_MENU_MODE_KEY] = mode
    return redirect("orders:internal_order_edit", order_id=order_id)


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_type_switch(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    order_type = request.POST.get("order_type")
    if order_type in Order.OrderType.values:
        try:
            order = change_internal_order_type(
                order=order, order_type=order_type, actor=request.user,
            )
        except ValidationError as error:
            messages.error(request, error.message)
            return redirect("orders:internal_order_edit", order_id=order.pk)
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
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    form = InternalOrderAutosaveForm(
        request.POST, order_total=order.total, for_print=request.POST.get("for_print") == "1",
    )
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    try:
        order = autosave_internal_order_customer(
            order=order, form_data=form.cleaned_data, actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    lookup_key = normalize_customer_phone(order.phone)
    duplicate = Customer.objects.filter(phone_key=lookup_key).exclude(pk=order.agenda_customer_id).first() if lookup_key else None
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
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    item = get_object_or_404(OrderItem, pk=item_id, order=order, item_type=OrderItem.ItemType.PACKAGE)
    form = InternalPackageExtrasForm(request.POST, existing_egg_id=item.egg_product_id)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Revisa los extras del paquete."}, status=400)
    try:
        update_internal_package_extras(
            order=order, item=item, cleaned_data=form.cleaned_data, actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_close_capture(request, order_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: el desarrollador pidió que "Imprimir cobro"
    # cierre la captura primero cuando haga falta (entrega sin forma de pago
    # elegida, o cualquier pedido cuyo saldo a favor ya cubra el total) — así el
    # ticket refleja números reales en vez de "Pendiente". Este endpoint ya
    # existía para un cierre directo con redirección; ahora también responde en
    # JSON cuando internal-order-form.js lo llama por fetch antes de imprimir,
    # sin duplicar la llamada a close_internal_order_capture. Borra esta nota.
    order = get_object_or_404(Order, pk=order_id)
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    try:
        close_internal_order_capture(order=order, actor=request.user)
    except ValidationError as error:
        if is_ajax:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        messages.error(request, error.message)
        return redirect("orders:internal_order_edit", order_id=order.pk)
    if is_ajax:
        return JsonResponse({"ok": True})
    messages.success(request, f"{order.formatted_number} quedó confirmado y continúa disponible para modificaciones.")
    return redirect("orders:order_list")


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_product_add(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    product = get_object_or_404(Product, pk=product_id)
    try:
        upgraded_package = add_water_to_internal_package(
            order=order, water_product=product, actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    if upgraded_package:
        order.refresh_from_db()
        return JsonResponse({
            "ok": True, "ticket": internal_order_ticket(order),
            "message": f"{upgraded_package.package_name_snapshot} ahora incluye agua.",
        })
    try:
        # Una pieza por vuelta; si alguna falla, ninguna queda registrada.
        with transaction.atomic():
            for raw_option_ids, comment in expanded_customizations(request.POST):
                add_internal_order_product(
                    order=order, product=product, actor=request.user,
                    raw_option_ids=raw_option_ids, comment=comment,
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
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
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
        with transaction.atomic():
            for raw_option_ids, comment in expanded_customizations(request.POST):
                add_internal_order_product(
                    order=order, product=product, actor=request.user, require_individual=False,
                    daily_menu=daily_menu, chicken_piece=request.POST.get("chicken_piece", ""),
                    raw_option_ids=raw_option_ids, comment=comment,
                )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_item_change(request, order_id, item_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    try:
        change_internal_order_item(
            order=order, item=item, action=request.POST.get("action"), actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    clear_internal_auto_meals(request, order.pk)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_note(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
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
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    item = get_object_or_404(OrderItem, pk=item_id, order=order)
    note = request.POST.get("note", "")
    if len(note) > 150:
        return JsonResponse({"ok": False, "error": "La nota del producto no puede exceder 150 caracteres."}, status=400)
    update_internal_order_item_note(order=order, item=item, note=note)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_tip_update(request, order_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta ruta es exclusiva de la captura interna
    # (Telefonista/Administrador) para registrar la propina de Transferencia antes de
    # despachar. Repartos usa su propio endpoint, más restrictivo. Borra esta nota.
    order = get_object_or_404(Order, pk=order_id)
    if not _can_edit_delivery_tip(order, request.user):
        return JsonResponse({
            "ok": False,
            "error": "Tu perfil no puede modificar la propina en el estado o método de pago actual.",
        }, status=403)
    form = DeliveryTipForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Escribe una propina válida."}, status=400)
    try:
        order = update_delivery_tip(
            order=order, amount=form.cleaned_data["tip_amount"], actor=request.user,
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({
        "ok": True, "tip_amount": f"{order.delivery_tip_amount:.2f}",
        "total_with_tip": f"{order.total_with_delivery_tip:.2f}",
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_auto_meal_add(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    product = get_object_or_404(Product, pk=product_id)
    daily_menu = get_object_or_404(
        DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    slot = internal_auto_meal_slot(product, daily_menu)
    if not slot:
        return JsonResponse({"ok": False, "error": "Este producto no puede formar un paquete."}, status=400)
    chicken_piece = request.POST.get("chicken_piece", "")
    package_extras = {
        "with_water": request.POST.get("with_water") == "1",
        "tortillas": request.POST.get("tortillas") == "1",
        "bread": request.POST.get("bread") == "1",
        "beans": request.POST.get("beans") == "1",
        "package_comment": " ".join(request.POST.get("package_comment", "").split()),
        "egg_product": selected_egg(request.POST.get("egg_product")),
    }
    previous_builders = copy.deepcopy(request.session.get(INTERNAL_AUTO_MEAL_SESSION_KEY, {}))
    package_created = False
    try:
        with transaction.atomic():
            for raw_option_ids, comment in expanded_customizations(request.POST):
                all_builders, builders, completed = plan_internal_auto_meal(
                    request, order.pk, slot, product.pk, chicken_piece,
                )
                # Los extras capturados (agua, frijoles, huevo...) acompañan sólo al
                # primer paquete que se complete, igual que al agregar de uno en uno.
                extras = package_extras if not package_created else {
                    "with_water": False, "tortillas": False, "bread": False,
                    "beans": False, "package_comment": "", "egg_product": None,
                }
                package_item = add_internal_auto_meal_component(
                    order=order, product=product, daily_menu=daily_menu,
                    completed_selection=completed, actor=request.user,
                    chicken_piece=(completed or {}).get("chicken_piece", chicken_piece),
                    raw_option_ids=raw_option_ids, comment=comment, **extras,
                )
                save_internal_auto_meals(request, order.pk, all_builders, builders)
                package_created = package_created or package_item is not None
    except ValidationError as error:
        request.session[INTERNAL_AUTO_MEAL_SESSION_KEY] = previous_builders
        request.session.modified = True
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({
        "ok": True, "ticket": internal_order_ticket(order),
        "auto_package_created": package_created,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_auto_meal_decrease(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    item = order.items.filter(
        product_id=product_id, item_type=OrderItem.ItemType.PRODUCT,
        is_package_candidate=True, is_customized=False,
    ).order_by("-id").first()
    if item:
        try:
            change_internal_order_item(
                order=order, item=item, action="decrease", actor=request.user,
            )
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
        clear_internal_auto_meals(request, order.pk)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_product_decrease(request, order_id, product_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    product = get_object_or_404(Product.objects.prefetch_related("option_groups__options"), pk=product_id)
    item = order.items.filter(
        product=product, item_type=OrderItem.ItemType.PRODUCT, is_customized=False,
        configuration_signature=resolve_product_selection(product)["signature"],
    ).first()
    if item:
        try:
            change_internal_order_item(
                order=order, item=item, action="decrease", actor=request.user,
            )
        except ValidationError as error:
            return JsonResponse({"ok": False, "error": error.message}, status=400)
    order.refresh_from_db()
    return JsonResponse({"ok": True, "ticket": internal_order_ticket(order)})


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def internal_order_package_add(request, order_id, package_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    package = get_object_or_404(MealPackage, pk=package_id, is_active=True)
    daily_menu = get_object_or_404(DailyMenu, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
    try:
        # Con el contador del diálogo llegan varios paquetes; si uno falla, ninguno queda.
        with transaction.atomic():
            for data, quantity in requested_packages(request.POST):
                form = InternalPackageForm(data, package=package, daily_menu=daily_menu, prefix=f"internal-package-{package.pk}")
                if not form.is_valid():
                    errors = [error["message"] for values in form.errors.get_json_data().values() for error in values]
                    raise ValidationError(" ".join(errors) or "Revisa todas las opciones del paquete.")
                apply_package_component_customizations(data, form.cleaned_data)
                for _ in range(quantity):
                    add_internal_order_package(
                        order=order, package=package, daily_menu=daily_menu,
                        cleaned_data=dict(form.cleaned_data),
                        packaging_quantities=parse_packaging_quantities(data),
                        actor=request.user,
                    )
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
    can_edit = can_manage and not _order_locked_for_edit(order, request.user)
    actions = [
        {"value": action, "label": ACTION_LABELS[action], "danger": action == "cancel"}
        for action in _order_actions_for_user(order, request.user)
    ] if can_manage else []
    # Pedido web sin ficha: clientes registrados con el mismo celular (sugerencia para asociar).
    agenda_matches = []
    if order.source == Order.Source.PUBLIC_WEB and not order.agenda_customer_id and can_manage:
        agenda_matches = list(
            Customer.objects.filter(phone_key=normalize_customer_phone(order.phone)).prefetch_related("addresses")
        ) if order.phone else []
    return render(request, "orders/order_detail.html", {
        "agenda_matches": agenda_matches,
        "show_agenda_panel": order.source == Order.Source.PUBLIC_WEB and not order.agenda_customer_id and can_manage,
        "order": order,
        "order_actions": actions,
        "can_edit_order": can_edit,
        "can_print_order": user_has_any_role(request.user, (ADMIN, WAITER, ORDER_TAKER)),
        "is_locked_for_user": _order_locked_for_edit(order, request.user),
        "can_complete_locked_delivery": (
            order.status == Order.Status.OUT_FOR_DELIVERY
            and user_has_any_role(request.user, (ORDER_TAKER,))
        ),
        "auto_print_job_id": request.GET.get("printed_job") if request.GET.get("printed_job", "").isdigit() else None,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def order_link_customer(request, order_id):
    """Pedido web: asociarlo a un cliente registrado (opcionalmente sustituyendo sus datos)
    o crear la ficha con lo que mandó el cliente."""
    order = get_object_or_404(Order, pk=order_id)
    customer = address = None
    if request.POST.get("action") != "create":
        customer = get_object_or_404(Customer, pk=request.POST.get("customer_id"))
        address_id = request.POST.get("address_id")
        address = customer.addresses.filter(pk=address_id).first() if address_id else customer.addresses.order_by("-updated_at").first()
    try:
        order = link_public_order_customer(order=order, actor=request.user, customer=customer, address=address)
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("orders:order_detail", order_id=order.pk)
    messages.success(request, f"{order.formatted_number} quedó asociado a {order.agenda_customer.name}.")
    return redirect("orders:order_detail", order_id=order.pk)


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def order_resolve(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    action = request.POST.get("action")
    if action == "cancel" and not user_has_any_role(request.user, (ADMIN,)):
        message = "Sólo un administrador puede cancelar pedidos."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": message}, status=403)
        messages.error(request, message)
        return redirect("orders:order_detail", order_id=order.pk)
    if action not in _order_actions_for_user(order, request.user):
        message = "Sólo un administrador puede reiniciar o modificar el ciclo de este pedido."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": message}, status=403)
        messages.error(request, message)
        return redirect("orders:order_detail", order_id=order.pk)
    try:
        order = transition_order(
            order=order, action=action, actor=request.user
        )
    except ValidationError as error:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            action = request.POST.get("action")
            if action == "dispatch_delivery":
                if user_has_any_role(request.user, (ADMIN,)):
                    recovery_url = f"{reverse('cashier:cashier_board')}?focus_order={order.pk}"
                    recovery_label = "Ir a Caja y asignar repartidor"
                else:
                    recovery_url = (
                        f"{reverse('deliveries:delivery_board')}"
                        f"?q={order.daily_number}&focus_order={order.pk}"
                    )
                    recovery_label = "Ir a Repartos y asignar repartidor"
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
            actions = [action for action in _order_actions_for_user(order, request.user) if action != "cancel"]
            next_action = actions[0] if actions else ""
            return JsonResponse({
                "ok": True, "status": order.status,
                "status_label": order.get_status_display(),
                "next_action": next_action,
                "next_action_label": ACTION_LABELS.get(next_action, ""),
                "changed_at": timezone.localtime().strftime("%d/%m/%Y %H:%M:%S"),
                "changed_by": request.user.get_full_name() or request.user.username,
            })
        messages.success(request, f"El pedido ahora está: {order.get_status_display()}.")
    if request.POST.get("return_to") == "list":
        return redirect("orders:order_list")
    return redirect("orders:order_detail", order_id=order.pk)


@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def delivery_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: un Repartidor sólo recibe pedidos todavía sin
    # dueño o asignados a su propia cuenta. Administrador y Telefonista conservan la
    # vista general, pero sólo Administrador podrá asignar a terceros. Borra esta nota.
    can_assign_any_delivery = user_has_any_role(request.user, (ADMIN,))
    is_delivery_profile = user_has_any_role(request.user, (DELIVERY,)) and not can_assign_any_delivery
    today = timezone.localdate()
    date_from = _report_date(request.GET.get("date_from"), today)
    date_to = _report_date(request.GET.get("date_to"), today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    search = request.GET.get("q", "").strip()
    exact_folio_query = _full_folio_search_query(search)
    # Sugerencias de la lupa: los repartos del rango (sin los demás filtros). Elegir uno
    # busca su folio completo, que muestra sólo ese pedido.
    suggestion_orders = Order.objects.filter(
        order_type=Order.OrderType.DELIVERY, operating_date__range=(date_from, date_to),
    ).select_related("delivery_person").order_by("-operating_date", "-daily_number")
    if is_delivery_profile:
        suggestion_orders = suggestion_orders.filter(delivery_person=request.user)
    search_options = []
    for order in suggestion_orders[:400]:
        person = order.delivery_person.get_full_name() or order.delivery_person.username if order.delivery_person else "Sin repartidor"
        address = " ".join(filter(None, (order.street, order.exterior_number)))
        search_options.append({
            "label": f"{order.formatted_number} · {order.customer_name or 'Sin nombre'}",
            "detail": " · ".join(filter(None, (address, order.neighborhood, person))),
            "search": " ".join(filter(None, (
                order.formatted_number, str(order.daily_number), order.customer_name, order.phone,
                address, order.neighborhood, person,
            ))),
            "url": f"{reverse('deliveries:delivery_board')}?{urlencode({'q': order.formatted_number})}",
        })
    delivery_orders = Order.objects.filter(order_type=Order.OrderType.DELIVERY)
    if exact_folio_query is not None:
        delivery_orders = delivery_orders.filter(exact_folio_query)
    else:
        delivery_orders = delivery_orders.filter(operating_date__range=(date_from, date_to))
    delivery_orders = delivery_orders.select_related(
        "delivery_person", "delivery_assigned_by", "delivery_tip_recipient",
        "delivery_tip_updated_by", "agenda_customer",
    ).prefetch_related("agenda_customer__debts")
    repartidores = get_user_model().objects.filter(
        is_active=True, groups__name=DELIVERY,
    ).distinct().order_by("first_name", "username")
    if is_delivery_profile:
        delivery_orders = delivery_orders.filter(delivery_person=request.user)
    selected_statuses = [value for value in request.GET.getlist("status") if value in Order.Status.values]
    delivery_person = request.GET.get("delivery_person", "").strip()
    if exact_folio_query is not None:
        selected_statuses = []
        if not is_delivery_profile:
            delivery_person = ""
    if search and exact_folio_query is None:
        number_query = _folio_search_query(search)
        delivery_orders = delivery_orders.filter(
            number_query | Q(customer_name__icontains=search) | Q(phone__icontains=search)
            | Q(street__icontains=search) | Q(exterior_number__icontains=search)
            | Q(neighborhood__icontains=search)
            | Q(delivery_person__first_name__icontains=search)
            | Q(delivery_person__last_name__icontains=search)
            | Q(delivery_person__username__icontains=search)
        )
    if selected_statuses and exact_folio_query is None:
        delivery_orders = delivery_orders.filter(status__in=selected_statuses)
    if exact_folio_query is None and not is_delivery_profile and delivery_person == "unassigned":
        delivery_orders = delivery_orders.filter(delivery_person__isnull=True)
    elif exact_folio_query is None and not is_delivery_profile and delivery_person.isdigit():
        delivery_orders = delivery_orders.filter(delivery_person_id=int(delivery_person))
    if is_delivery_profile:
        # NOTA TEMPORAL PARA APRENDIZAJE: para el Repartidor, las entregas que aún
        # requieren su acción van primero. Dentro de ese bloque respetamos el orden
        # en que Caja las liberó; las ya entregadas bajan al final sin desaparecer.
        # La prioridad se calcula en la base para que sea estable al recargar.
        # Borra esta nota después de leerla.
        delivery_orders = delivery_orders.annotate(
            delivery_action_priority=Case(
                When(status=Order.Status.OUT_FOR_DELIVERY, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by(
            "delivery_action_priority", "cashier_released_at", "created_at", "id",
        )
    delivery_orders = list(delivery_orders)
    for order in delivery_orders:
        # NOTA TEMPORAL PARA APRENDIZAJE: la misma regla que protege los POST
        # decide qué controles se dibujan. Así no ofrecemos botones que el
        # servidor tendría que rechazar cuando el pedido ya salió. Borra esta nota.
        order.is_locked_for_user = _order_locked_for_edit(order, request.user)
        order.customer_debt_note = _order_debt_badge(order)
        order.can_edit_delivery_tip = _can_edit_delivery_tip_on_board(order, request.user)
        order.can_assign_delivery = can_assign_any_delivery and not order.is_locked_for_user
        order.can_update_delivery_status = (
            order.status in {Order.Status.READY, Order.Status.OUT_FOR_DELIVERY}
            if not is_delivery_profile
            # NOTA TEMPORAL PARA APRENDIZAJE: el Repartidor sólo ve sus propios
            # pedidos aquí (delivery_orders ya está filtrado arriba), así que sólo
            # falta exigir que siga "En reparto": no puede despachar (READY), sólo
            # completar. Esto aplica igual a Efectivo, Terminal y Transferencia; la
            # devolución del efectivo continúa conciliándose por separado en Caja.
            # Borra esta nota después de leerla.
            else order.status == Order.Status.OUT_FOR_DELIVERY
        )
        # NOTA TEMPORAL PARA APRENDIZAJE: Administrador y Telefonista pueden mover el
        # pedido por cualquier estado válido directamente desde Repartos (igual que ya
        # puede Administrador desde Caja) — Repartidor no tiene motivo para verlo, ya
        # tiene su propio botón de despachar/completar de arriba. Borra esta nota.
        if not is_delivery_profile:
            actions = [action for action in _order_actions_for_user(order, request.user) if action != "cancel"]
            order.quick_action = actions[0] if actions else ""
            order.quick_action_label = ACTION_LABELS.get(order.quick_action, "")
    return render(request, "orders/delivery_board.html", {
        "delivery_orders": delivery_orders,
        "search_options": search_options,
        "repartidores": repartidores,
        "status_choices": Order.Status.choices,
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
        "cash_denominations": [50, 100, 150, 200, 500],
        "search": search, "selected_statuses": selected_statuses,
        "selected_delivery_person": delivery_person,
        "can_assign_any_delivery": can_assign_any_delivery,
        "is_delivery_profile": is_delivery_profile,
        "date_from": date_from,
        "date_to": date_to,
    })


@require_POST
@role_required(ADMIN)
def delivery_assign(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if _order_locked_for_edit(order, request.user):
        return _locked_order_response(request, order)
    delivery_person_id = request.POST.get("delivery_person", "").strip()
    delivery_person = get_object_or_404(
        get_user_model(), pk=delivery_person_id,
    ) if delivery_person_id else None
    # NOTA TEMPORAL PARA APRENDIZAJE: esta validación protege aunque alguien fabrique
    # el POST manualmente. Un Repartidor sólo puede elegirse a sí mismo y tomar una
    # entrega sin dueño o que ya sea suya. Borra esta nota después de leerla.
    if delivery_person is not None and not user_has_any_role(request.user, (ADMIN,)) and (
        delivery_person.pk != request.user.pk
        or order.delivery_person_id not in (None, request.user.pk)
    ):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Sólo puedes asignarte pedidos disponibles a tu propio perfil."}, status=403)
        raise PermissionDenied
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
            display_name = (
                order.delivery_person.get_full_name() or order.delivery_person.username
                if order.delivery_person else "Sin asignar"
            )
            return JsonResponse({
                "ok": True, "delivery_person_id": order.delivery_person_id or "",
                "delivery_person_name": display_name,
                "message": (
                    f"{display_name} quedó asignado a {order.formatted_number}."
                    if order.delivery_person else f"{order.formatted_number} quedó sin repartidor asignado."
                ),
            })
        messages.success(request, f"El repartidor de {order.formatted_number} fue actualizado.")
    return redirect("deliveries:delivery_board")


@require_POST
@role_required(ADMIN, DELIVERY)
def delivery_tip_update(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _can_edit_delivery_tip_on_board(order, request.user):
        return JsonResponse({
            "ok": False,
            "error": "Tu perfil no puede modificar la propina en el estado o método de pago actual.",
        }, status=403)
    is_delivery_profile = (
        user_has_any_role(request.user, (DELIVERY,))
        and not user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    )
    if is_delivery_profile and order.delivery_person_id != request.user.pk:
        return JsonResponse({"ok": False, "error": "Sólo puedes modificar propinas de pedidos asignados a ti."}, status=403)
    if is_delivery_profile and order.delivery_tip_updated_at is not None:
        return JsonResponse({"ok": False, "error": "La propina ya fue registrada y no puede editarse."}, status=400)
    # NOTA TEMPORAL PARA APRENDIZAJE: aquí ya no se bloquea Entregado a secas —
    # _can_edit_delivery_tip_on_board (arriba) ya decide correctamente según el
    # método de pago (Efectivo sigue exigiendo "En reparto"; Terminal también
    # permite "Entregado", porque el propio Repartidor marca esa transición).
    # Borra esta nota después de leerla.
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
    is_delivery_profile = (
        user_has_any_role(request.user, (DELIVERY,))
        and not user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    )
    # NOTA TEMPORAL PARA APRENDIZAJE: el Repartidor puede cerrar su propio pedido de
    # En reparto a Entregado con cualquier forma de pago. En Efectivo esto no confirma
    # que haya devuelto el dinero: `cash_settlement_confirmed` sigue siendo un control
    # independiente de Caja. El Repartidor tampoco inicia ni reinicia ciclos; sólo
    # puede completar (nunca despachar) el pedido asignado a él. Borra esta nota.
    if is_delivery_profile:
        is_own_order = order.delivery_person_id == request.user.pk
        if not is_own_order:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "El repartidor no puede cambiar el estado de este pedido."}, status=403)
            raise PermissionDenied
    action = (
        "complete_delivery"
        if is_delivery_profile or order.status == Order.Status.OUT_FOR_DELIVERY
        else "dispatch_delivery"
    )
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
        "status": order.status,
        "status_label": order.get_status_display(),
        "payment_method": order.payment_method,
        "payment_label": order.get_payment_method_display() if order.payment_method else "Sin definir",
        "cash_tendered": f"{order.cash_tendered:.2f}" if order.cash_tendered is not None else "",
        "needs_change": order.needs_change,
        "change_required": f"{order.change_required:.2f}" if order.change_required is not None else "",
        "cash_settlement_confirmed": order.cash_settlement_confirmed,
        "tip_amount": f"{order.delivery_tip_amount:.2f}",
        "total_with_tip": f"{order.total_with_delivery_tip:.2f}",
    }


@role_required(ADMIN, WAITER, ORDER_TAKER)
def order_kitchen_print(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("created_by", "delivery_person"), pk=order_id,
    )
    context = order_print_context(order)
    context.update({
        "items": [printable_item(item) for item in order.items.all()],
        "back_url": reverse("orders:order_detail", args=(order.pk,)),
    })
    return render(request, "printing/kitchen_ticket.html", context)


@role_required(ADMIN, WAITER, ORDER_TAKER)
def order_kitchen_custom_print(request, order_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta variante deja escoger partidas y cantidades;
    # la impresión normal de cocina abre el ticket completo. Borra esta nota al leerla.
    order = get_object_or_404(
        Order.objects.select_related("created_by", "delivery_person"), pk=order_id,
    )
    queryset = order.items.select_related("product", "package").all()
    selected, result = selected_printable_items(request, queryset)
    context = order_print_context(order)
    context["back_url"] = reverse("orders:order_detail", args=(order.pk,))
    if request.method == "POST" and selected is not None and not result:
        try:
            job = queue_ticket(source_type="order", source=order, ticket_type="kitchen", items=selected, user=request.user)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("orders:order_detail", order_id=order.pk)
        messages.success(request, f"Comanda enviada a la Dell (trabajo #{job.pk}).")
        return redirect(f"{reverse('orders:order_detail', args=(order.pk,))}?printed_job={job.pk}")
    context.update({
        "selection_items": [printable_item(item) for item in queryset],
        "selection_errors": result if request.method == "POST" else [],
        "submit_url": reverse("orders:order_kitchen_custom_print", args=(order.pk,)),
    })
    return render(request, "printing/kitchen_select.html", context)


@role_required(ADMIN, WAITER, ORDER_TAKER)
def order_payment_print(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("created_by", "delivery_person"), pk=order_id,
    )
    context = order_print_context(order)
    context.update({
        "items": [printable_item(item) for item in order.items.all()],
        "back_url": reverse("orders:order_detail", args=(order.pk,)),
    })
    return render(request, "printing/payment_ticket.html", context)


@role_required(ADMIN, ORDER_TAKER)
def cashier_debt_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: Telefonista comparte esta consulta para poder
    # advertir al cliente, pero can_manage_debts mantiene todos los formularios de
    # cobro exclusivamente en Administrador. Borra esta nota después de leerla.
    debts = CustomerDebt.objects.select_related(
        "customer", "order", "created_by",
    ).prefetch_related("movements__registered_by")
    search = request.GET.get("q", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    # Sugerencias de la lupa: cada adeudo (cliente, teléfono y folio). Elegir uno muestra
    # ese pedido del cliente, esté pendiente o ya cerrado.
    search_options = [
        {
            "label": f"{debt.customer.name} · {debt.order.formatted_number}",
            "detail": " · ".join(filter(None, (
                debt.customer.phone, f"Debe ${debt.balance:.2f}", debt.get_status_display(),
            ))),
            "search": f"{debt.customer.name} {debt.customer.phone} {debt.order.customer_name} {debt.order.formatted_number} {debt.order.daily_number}",
            "url": f"{reverse('cashier:debt_board')}?{urlencode({'customer': debt.customer_id, 'q': debt.order.formatted_number, 'scope': 'all'})}",
        }
        for debt in CustomerDebt.objects.select_related("customer", "order").order_by("-created_at")[:500]
    ]
    scope = request.GET.get("scope", "active")
    # NOTA TEMPORAL PARA APRENDIZAJE: a diferencia de Pedidos/Repartos/Caja, aquí el
    # default de fecha es "todas" (un adeudo puede llevar semanas sin resolverse y no
    # queremos que desaparezca de la vista sólo por no ser de hoy). Si el operador sí
    # captura una fecha, se respeta. Borra esta nota después de leerla.
    date_from = _report_date(request.GET.get("date_from"), None)
    date_to = _report_date(request.GET.get("date_to"), None)
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    if date_from:
        debts = debts.filter(order__operating_date__gte=date_from)
    if date_to:
        debts = debts.filter(order__operating_date__lte=date_to)
    if search:
        debt_search = (
            Q(customer__name__icontains=search) | Q(customer__phone__icontains=search)
            | Q(order__customer_name__icontains=search)
        )
        digits = search.lstrip("#")
        if digits.isdigit():
            debt_search |= Q(order__daily_number=int(digits))
            if len(digits) >= 5:
                debt_search |= Q(
                    order__operating_date__day=int(digits[:2]),
                    order__operating_date__month=int(digits[2:4]),
                    order__daily_number=int(digits[4:]),
                )
        debts = debts.filter(debt_search)
    if customer_id.isdigit():
        debts = debts.filter(customer_id=int(customer_id))
    if scope == "closed":
        debts = debts.filter(status__in=(CustomerDebt.Status.PAID, CustomerDebt.Status.FORGIVEN))
    elif scope == "all":
        pass
    else:
        scope = "active"
        debts = debts.filter(status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL))
    debts = list(debts)
    return render(request, "orders/cashier_debt_board.html", {
        "debts": debts, "search": search, "selected_scope": scope, "search_options": search_options,
        "date_from": date_from, "date_to": date_to,
        "can_manage_debts": user_has_any_role(request.user, (ADMIN,)),
        "can_apply_credit": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
        "original_total": sum((debt.original_amount for debt in debts), Decimal("0")),
        "paid_total": sum((debt.paid_amount for debt in debts), Decimal("0")),
        "balance_total": sum((debt.balance for debt in debts if debt.status != CustomerDebt.Status.FORGIVEN), Decimal("0")),
    })


@require_POST
@role_required(ADMIN)
def cashier_debt_create(request):
    reference = request.POST.get("order_reference", "").strip()
    if not reference.lstrip("#").isdigit():
        messages.error(request, "Escribe un folio numérico válido.")
        return redirect("cashier:debt_board")
    candidates = Order.objects.filter(_folio_search_query(reference)).order_by("-operating_date", "-id")
    order = candidates.first()
    if not order:
        messages.error(request, "No encontramos un pedido con ese folio.")
        return redirect("cashier:debt_board")
    try:
        debt = create_customer_debt(order=order, actor=request.user, note=request.POST.get("note", ""))
    except ValidationError as error:
        messages.error(request, error.message)
        return redirect("cashier:debt_board")
    messages.success(request, f"{order.formatted_number} quedó a cuenta de {debt.customer.name}.")
    board_url = f"{reverse('cashier:debt_board')}?customer={debt.customer_id}"
    if debt.customer.credit_balance > 0:
        return redirect(credit_apply_url(debt.customer_id, board_url, debt.pk))
    return redirect(board_url)


def _debt_customer_from_request(request):
    customer_id = request.POST.get("customer_id", "")
    if customer_id.isdigit():
        return get_object_or_404(Customer, pk=customer_id)
    name = " ".join(request.POST.get("new_customer_name", "").split())
    phone = request.POST.get("new_customer_phone", "").strip()
    if not name:
        return None
    existing = customer_with_phone(phone)
    if existing:
        raise ValidationError(f"El celular {phone} ya pertenece a {existing.name}. Elígelo en el buscador.")
    return Customer.objects.create(name=name, phone=phone)


@role_required(ADMIN, ORDER_TAKER)
def customer_duplicates(request):
    """Depuración: clientes que comparten celular. Se elige cuál se queda; los demás se
    eliminan pasando antes su historial al que se queda."""
    if request.method == "POST":
        keep = get_object_or_404(Customer, pk=request.POST.get("keep_id") or 0)
        others = list(Customer.objects.filter(phone_key=keep.phone_key).exclude(pk=keep.pk)) if keep.phone_key else []
        removed = merge_customers(keep=keep, others=others)
        messages.success(request, f"Quedó {keep.name}; se unieron y eliminaron {removed} cliente{'s' if removed != 1 else ''} con el mismo celular.")
        return redirect("orders:customer_duplicates")
    return render(request, "orders/customer_duplicates.html", {"groups": duplicate_customer_groups()})


@require_POST
@role_required(ADMIN)
def cashier_order_debt_create(request, order_id):
    """Register a visible order as unpaid without making Caja retype its folio."""
    # NOTA TEMPORAL PARA APRENDIZAJE: los botones de Pedidos y Cambios reutilizan el
    # servicio central para compartir reglas de cliente, estado y pedido único.
    # Borra esta nota después de leerla.
    order = get_object_or_404(Order, pk=order_id)
    try:
        # Pedido sin cliente de la agenda: el panel de "No pagó" manda el cliente elegido
        # (customer_id) o los datos de uno nuevo (new_customer_name / new_customer_phone).
        with transaction.atomic():
            if not order.agenda_customer_id:
                customer = _debt_customer_from_request(request)
                if customer:
                    order.agenda_customer = customer
                    order.save(update_fields=("agenda_customer", "updated_at"))
            debt = create_customer_debt(
                order=order, actor=request.user,
                note=request.POST.get("note", "Pedido reportado como no pagado."),
            )
    except ValidationError as error:
        messages.error(request, error.message)
        debt = None
    else:
        messages.success(
            request,
            f"{order.formatted_number} quedó registrado como no pagado a nombre de {debt.customer.name}.",
        )
    next_url = request.POST.get("next", "")
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = reverse("cashier:debt_board")
    if debt and debt.customer.credit_balance > 0:
        return redirect(credit_apply_url(debt.customer_id, next_url, debt.pk))
    return redirect(next_url)


@require_POST
@role_required(ADMIN)
def cashier_debt_payment(request, debt_id):
    debt = get_object_or_404(CustomerDebt, pk=debt_id)
    try:
        debt = register_customer_debt_payment(
            debt=debt, amount=request.POST.get("amount", ""),
            payment_method=request.POST.get("payment_method", ""), actor=request.user,
            note=request.POST.get("note", ""),
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"Abono registrado. Saldo de {debt.customer.name}: ${debt.balance:.2f}.")
    return redirect(f"{reverse('cashier:debt_board')}?customer={debt.customer_id}&scope=all")


@require_POST
@role_required(ADMIN)
def cashier_settle_debts(request, order_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: el desarrollador pidió que, cuando un cliente
    # con adeudo previo trae un pedido nuevo, Caja pueda cobrar ambas cosas juntas
    # sin ir aparte a Cuentas por cobrar — el pedido nuevo se cobra como siempre
    # (botones de arriba, sin cambios); este formulario aparte sólo cobra el
    # adeudo viejo, asociando todos sus pedidos pendientes, sólo algunos, o el
    # monto que el cajero indique. Borra esta nota después de leerla.
    order = get_object_or_404(Order, pk=order_id)
    if not order.agenda_customer_id:
        messages.error(request, "Este pedido no tiene un cliente de la agenda vinculado.")
    else:
        try:
            settle_selected_debts_from_cashier(
                customer=order.agenda_customer, debt_ids=request.POST.getlist("debt_ids"),
                amount=request.POST.get("amount", ""), payment_method=request.POST.get("payment_method", ""),
                actor=request.user, note=f"Cobrado junto con el pedido {order.formatted_number}",
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, f"Se registró el cobro de adeudo de {order.agenda_customer.name}.")
    next_url = request.POST.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect("cashier:cashier_board")


@require_POST
@role_required(ADMIN)
def cashier_debt_status(request, debt_id):
    debt = get_object_or_404(CustomerDebt, pk=debt_id)
    try:
        debt = set_customer_debt_forgiven(
            debt=debt, forgiven=request.POST.get("action") == "forgive",
            actor=request.user, note=request.POST.get("note", ""),
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"El adeudo de {debt.customer.name} ahora está {debt.get_status_display().lower()}.")
    return redirect(f"{reverse('cashier:debt_board')}?customer={debt.customer_id}&scope=all")


@role_required(ADMIN, ORDER_TAKER)
def cashier_credit_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: a diferencia de CustomerDebt, el saldo a favor
    # vive a nivel cliente (no de un pedido en particular), así que este panel lista
    # clientes con saldo en vez de movimientos sueltos. Telefonista puede consultarlo
    # para avisar al cliente; sólo Administrador puede registrar depósitos/devoluciones.
    # Borra esta nota después de leerla.
    customers = Customer.objects.filter(credit_balance__gt=0).order_by("name")
    search = request.GET.get("q", "").strip()
    if search:
        customers = customers.filter(Q(name__icontains=search) | Q(phone__icontains=search))
    customers = list(customers)
    customer_id = request.GET.get("customer", "").strip()
    selected_customer = None
    movements = []
    if customer_id.isdigit():
        selected_customer = Customer.objects.filter(pk=int(customer_id)).first()
        if selected_customer:
            # NOTA TEMPORAL PARA APRENDIZAJE: el desarrollador pidió ver el historial
            # como un balance corrido — con cuánto saldo empezó cada movimiento y con
            # cuánto quedó — no sólo la lista de movimientos sueltos que ya había.
            # Como Customer.credit_balance es sólo el total actual (cacheado), aquí se
            # reconstruye el saldo en cada punto recorriendo TODO el historial en
            # orden cronológico (el más viejo primero) y sumando/restando cada
            # movimiento; por eso no se trunca a los últimos 50 como antes — un
            # balance corrido incompleto mentiría sobre el saldo inicial. Se muestra
            # en la plantilla del más reciente al más viejo (para ver primero lo
            # último que pasó), pero el cálculo siempre corre de más viejo a más
            # nuevo. Borra esta nota después de leerla.
            movements = list(
                selected_customer.credit_movements.select_related("order", "registered_by")
                .order_by("created_at", "id")
            )
            running_balance = Decimal("0")
            for movement in movements:
                movement.balance_before = running_balance
                if movement.action == CustomerCreditMovement.Action.DEPOSIT:
                    running_balance += movement.amount
                else:
                    running_balance -= movement.amount
                movement.balance_after = running_balance
            movements.reverse()
    owing_ids = set(CustomerDebt.objects.filter(
        customer__in=customers,
        status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL),
    ).values_list("customer_id", flat=True))
    for customer in customers:
        customer.has_open_debts = customer.pk in owing_ids
    return render(request, "orders/cashier_credit_board.html", {
        "customers": customers, "search": search,
        "can_manage_credit": user_has_any_role(request.user, (ADMIN,)),
        "can_apply_credit": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
        "balance_total": sum((customer.credit_balance for customer in customers), Decimal("0")),
        "selected_customer": selected_customer, "movements": movements,
    })


def credit_apply_url(customer_id, next_url, debt_id=None):
    """Pantalla para pagar adeudos con saldo a favor; al terminar regresa a `next_url`."""
    params = {"next": next_url}
    if debt_id:
        params["debt"] = debt_id
    return f"{reverse('cashier:credit_apply', args=(customer_id,))}?{urlencode(params)}"


@role_required(ADMIN, ORDER_TAKER, WAITER)
def cashier_credit_apply(request, customer_id):
    """Pagar adeudos del cliente con su saldo a favor.

    Aparece sola tras registrar un depósito (si el cliente debe pedidos) o un
    "no pagó" (si el cliente tiene saldo a favor); también se abre desde la ficha
    del cliente, Adeudos y Saldos a favor. El mesero sólo ve la cuenta que acaba de
    dejar a nombre del cliente (`?debt=`).
    """
    customer = get_object_or_404(Customer, pk=customer_id)
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not (next_url.startswith("/") and not next_url.startswith("//")):
        next_url = f"{reverse('cashier:debt_board')}?customer={customer.pk}"
    raw_focus = request.POST.get("debt") or request.GET.get("debt") or ""
    focus_id = int(raw_focus) if raw_focus.isdigit() else None
    debts = open_customer_debts(customer)
    if not user_has_any_role(request.user, (ADMIN, ORDER_TAKER)):
        debts = [debt for debt in debts if debt.pk == focus_id]
    if customer.credit_balance <= 0 or not debts:
        return redirect(next_url)
    suggestion = suggested_credit_allocation(
        credit=customer.credit_balance, debts=debts, focus_debt_id=focus_id,
    )
    if request.method == "POST":
        allocations = {
            debt.pk: request.POST.get(f"amount_{debt.pk}", "0") if request.POST.get(f"apply_{debt.pk}") else "0"
            for debt in debts
        }
        try:
            apply_credit_to_debts(customer=customer, allocations=allocations, actor=request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            # Se vuelve a mostrar lo que se capturó para corregirlo.
            suggestion = {}
            for debt in debts:
                try:
                    suggestion[debt.pk] = Decimal(str(allocations[debt.pk] or "0"))
                except Exception:
                    suggestion[debt.pk] = Decimal("0")
        else:
            customer.refresh_from_db()
            messages.success(
                request,
                f"Se pagaron pedidos de {customer.name} con su saldo a favor. "
                f"Saldo restante: ${customer.credit_balance:.2f}.",
            )
            return redirect(next_url)
    rows = [{"debt": debt, "amount": suggestion[debt.pk]} for debt in debts]
    rows.sort(key=lambda row: row["debt"].pk != focus_id)
    return render(request, "orders/cashier_credit_apply.html", {
        "customer": customer, "rows": rows, "next_url": next_url, "focus_id": focus_id,
        "debt_total": sum((debt.balance for debt in debts), Decimal("0")),
    })


@require_POST
@role_required(ADMIN)
def cashier_credit_deposit(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: customer_id llega lleno cuando el operador
    # eligió una sugerencia del buscador (customer-picker.js) — en ese caso no hay
    # ambigüedad y se usa directo. Si llega vacío (JS deshabilitado, o escribió y no
    # seleccionó nada), se recurre a la búsqueda difusa de antes como respaldo.
    # Borra esta nota después de leerla.
    customer_id = request.POST.get("customer_id", "").strip()
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id.isdigit() else None
    if not customer:
        query = request.POST.get("customer_query", "").strip()
        if not query:
            messages.error(request, "Escribe el nombre o teléfono del cliente.")
            return redirect("cashier:credit_board")
        candidates = list(Customer.objects.filter(Q(name__icontains=query) | Q(phone__icontains=query))[:2])
        if not candidates:
            messages.error(request, "No encontramos un cliente con ese nombre o teléfono. Regístralo primero en Clientes.")
            return redirect("cashier:credit_board")
        if len(candidates) > 1:
            messages.error(request, "Hay más de un cliente que coincide; selecciónalo de la lista o sé más específico.")
            return redirect("cashier:credit_board")
        customer = candidates[0]
    try:
        add_customer_credit(
            customer=customer, amount=request.POST.get("amount", ""),
            payment_method=request.POST.get("payment_method", ""), actor=request.user,
            note=request.POST.get("note", ""),
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"Depósito registrado para {customer.name}.")
        if open_customer_debts(customer):
            return redirect(credit_apply_url(customer.pk, f"{reverse('cashier:credit_board')}?customer={customer.pk}"))
    return redirect(f"{reverse('cashier:credit_board')}?customer={customer.pk}")


@require_POST
@role_required(ADMIN)
def cashier_credit_refund(request, customer_id):
    customer = get_object_or_404(Customer, pk=customer_id)
    try:
        refund_customer_credit(
            customer=customer, amount=request.POST.get("amount", ""),
            actor=request.user, note=request.POST.get("note", ""),
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, f"Devolución registrada para {customer.name}.")
    return redirect(f"{reverse('cashier:credit_board')}?customer={customer.pk}")


@role_required(ADMIN)
def cashier_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: Caja sólo carga pedidos operativos; las entregas
    # aparecen primero porque concentran asignación, forma de pago y entrega de cambio.
    # Los filtros ayudan sin convertir este panel en otro historial. Borra esta nota.
    active_statuses = (
        Order.Status.PENDING_CONFIRMATION, Order.Status.CONFIRMED, Order.Status.SCHEDULED,
        Order.Status.PREPARING, Order.Status.READY, Order.Status.OUT_FOR_DELIVERY,
    )
    # NOTA TEMPORAL PARA APRENDIZAJE: "Todos" no significa "todo el historial" aquí,
    # sino "todos los estados del día que se está operando" — la fecha (hoy por
    # defecto) siempre manda primero; el alcance sólo decide si además se exige que
    # sigan activos y sin liberar de caja. Borra esta nota después de leerla.
    today = timezone.localdate()
    date_from = _report_date(request.GET.get("date_from"), today)
    date_to = _report_date(request.GET.get("date_to"), today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    scope = request.GET.get("scope", "active").strip()
    search = request.GET.get("q", "").strip()
    exact_folio_query = _full_folio_search_query(search)
    if exact_folio_query is not None:
        queryset = Order.objects.filter(exact_folio_query)
    else:
        queryset = Order.objects.filter(operating_date__range=(date_from, date_to))
        if scope == "all":
            pass
        else:
            scope = "active"
            queryset = queryset.filter(status__in=active_statuses, cashier_released_at__isnull=True)
    queryset = queryset.select_related(
        "delivery_person", "cash_settlement_by", "customer_debt", "agenda_customer",
    ).prefetch_related("items", "agenda_customer__debts__order").annotate(has_pending_notification=_pending_notification())
    queryset = _operational_board_ordering(queryset)
    order_type = request.GET.get("type", "").strip()
    delivery_person = request.GET.get("delivery_person", "").strip()
    payment_method = request.GET.get("payment_method", "").strip()
    if exact_folio_query is not None:
        scope = "all"
        order_type = ""
        delivery_person = ""
        payment_method = ""
    if search and exact_folio_query is None:
        queryset = queryset.filter(
            _folio_search_query(search) | Q(customer_name__icontains=search)
            | Q(phone__icontains=search) | Q(street__icontains=search)
            | Q(exterior_number__icontains=search)
        )
    if exact_folio_query is None and order_type in Order.OrderType.values:
        queryset = queryset.filter(order_type=order_type)
    if exact_folio_query is None and delivery_person == "unassigned":
        queryset = queryset.filter(delivery_person__isnull=True)
    elif exact_folio_query is None and delivery_person.isdigit():
        queryset = queryset.filter(delivery_person_id=int(delivery_person))
    if exact_folio_query is None and payment_method == "undefined":
        queryset = queryset.filter(payment_method="")
    elif exact_folio_query is None and payment_method in Order.PaymentMethod.values:
        queryset = queryset.filter(payment_method=payment_method)
    orders = list(queryset)
    # NOTA TEMPORAL PARA APRENDIZAJE: Caja reutiliza la misma máquina de estados que
    # Pedidos. Sólo preparamos aquí el siguiente botón permitido; la validación real
    # continúa dentro de transition_order. Borra esta nota después de leerla.
    for order in orders:
        actions = [action for action in _order_actions_for_user(order, request.user) if action != "cancel"]
        order.quick_action = actions[0] if actions else ""
        order.quick_action_label = ACTION_LABELS.get(order.quick_action, "")
        order.can_cancel = (
            user_has_any_role(request.user, (ADMIN,))
            and order.status not in {Order.Status.CANCELED, Order.Status.PICKED_UP, Order.Status.DELIVERED}
        )
        order.can_mark_unpaid = (
            order.status != Order.Status.CANCELED and not hasattr(order, "customer_debt")
        )
        order.customer_debt_note = _order_debt_badge(order)
    repartidores = get_user_model().objects.filter(
        is_active=True, groups__name=DELIVERY,
    ).distinct().order_by("first_name", "username")
    return render(request, "orders/cashier_board.html", {
        "delivery_orders": [order for order in orders if order.order_type == Order.OrderType.DELIVERY],
        "pickup_orders": [order for order in orders if order.order_type == Order.OrderType.PICKUP],
        "repartidores": repartidores, "search": search, "selected_type": order_type,
        "selected_delivery_person": delivery_person,
        "selected_payment_method": payment_method,
        "payment_method_choices": Order.PaymentMethod.choices,
        "selected_scope": scope,
        "date_from": date_from,
        "date_to": date_to,
        "order_search_options": _board_order_search_options(date_from, date_to),
    })


def _report_date(value, fallback):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


@role_required(ADMIN)
def cashier_coffee_report(request):
    selected_date = _report_date(request.GET.get("date"), timezone.localdate())
    report = coffee_sales_for_date(selected_date)
    settlements = list(CoffeeSettlement.objects.filter(operating_date=selected_date).select_related("recorded_by"))
    paid_total = sum((entry.amount for entry in settlements), Decimal("0.00"))
    if request.GET.get("download") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="bebidas_calientes_{selected_date.isoformat()}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(("Producto", "Tamaño", "Leche", "Cantidad", "Precio unitario", "Total"))
        for row in report["summary"]:
            writer.writerow((row["product"], row["size"], row["milk"], row["quantity"], row["unit_price"], row["total"]))
        writer.writerow(("TOTAL COBRABLE", "", "", "", "", report["sales_total"]))
        writer.writerow(("ENTREGADO AL BARISTA", "", "", "", "", paid_total))
        writer.writerow(("SALDO", "", "", "", "", report["sales_total"] - paid_total))
        writer.writerow(())
        writer.writerow(("DETALLE DE TICKETS",))
        writer.writerow(("Origen", "Folio o mesa", "Producto", "Tamaño", "Leche", "Cantidad", "Precio unitario", "Total", "Estado"))
        for row in report["details"]:
            writer.writerow((row["source"], row["reference"], row["product"], row["size"], row["milk"], row["quantity"], row["unit_price"], row["total"], "Finalizada" if row["finalized"] else "Abierta"))
        return response
    return render(request, "orders/cashier_coffee_report.html", {
        **report, "selected_date": selected_date, "settlements": settlements,
        "paid_total": paid_total, "balance": report["sales_total"] - paid_total,
    })


@require_POST
@role_required(ADMIN)
def cashier_coffee_settlement(request):
    selected_date = _report_date(request.POST.get("date"), None)
    try:
        amount = Decimal(request.POST.get("amount", ""))
    except (TypeError, ValueError, ArithmeticError):
        amount = None
    if not selected_date or amount is None or not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount >= Decimal("100000000"):
        messages.error(request, "Indica una fecha y un monto válido mayor a cero.")
        return redirect("cashier:coffee_report")
    report = coffee_sales_for_date(selected_date)
    paid = sum(CoffeeSettlement.objects.filter(operating_date=selected_date).values_list("amount", flat=True), Decimal("0.00"))
    if amount > report["sales_total"] - paid:
        messages.error(request, "La entrega no puede superar el saldo cobrable.")
    else:
        CoffeeSettlement.objects.create(
            operating_date=selected_date, amount=amount,
            note=request.POST.get("note", "").strip()[:250], recorded_by=request.user,
        )
        messages.success(request, "Entrega al barista registrada.")
    return redirect(f'{reverse("cashier:coffee_report")}?date={selected_date.isoformat()}')


def _cash_register_audit_querysets(selected_date):
    unpaid_orders = CustomerDebt.objects.filter(
        order__operating_date=selected_date,
        status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL),
    )
    pending_orders = Order.objects.filter(
        operating_date=selected_date,
    ).exclude(status=Order.Status.CANCELED).exclude(
        status__in=(Order.Status.DELIVERED, Order.Status.PICKED_UP),
    ).exclude(
        status=Order.Status.TRANSFERRED,
        transferred_to_table__status=TableAccount.Status.CLOSED,
    ).exclude(customer_debt__isnull=False)
    return unpaid_orders, pending_orders


@require_GET
@role_required(ADMIN)
def cashier_register_cut_audit_counts(request):
    selected_date = _report_date(request.GET.get("date"), timezone.localdate())
    unpaid_orders, pending_orders = _cash_register_audit_querysets(selected_date)
    return JsonResponse({
        "unpaid_count": unpaid_orders.count(),
        "pending_count": pending_orders.count(),
    })


@role_required(ADMIN)
def cashier_register_cut(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: el desarrollador pidió un corte de caja
    # general (distinto de "Corte de terminales", que sólo concilia Clover/
    # Mercado Pago/Transferencias contra lo que ya registró la app) — aquí lo
    # que importa es el efectivo físico con el que se abrió/cerró el día, los
    # egresos pagados directo de caja, y una auditoría de que ningún pedido se
    # haya quedado sin resolver. Los 4 importes nunca se "bloquean" — se pueden
    # corregir cualquier día, por eso no hay concepto de abierto/cerrado aquí.
    # Borra esta nota después de leerla.
    today = timezone.localdate()
    selected_date = _report_date(request.GET.get("date"), today)
    cut, _ = CashRegisterCut.objects.get_or_create(operating_date=selected_date)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_amounts":
            try:
                update_cash_register_cut(
                    cut=cut,
                    opening_cash=request.POST.get("opening_cash", ""),
                    closing_cash=request.POST.get("closing_cash", ""),
                    closing_card=request.POST.get("closing_card", ""),
                    closing_transfer=request.POST.get("closing_transfer", ""),
                    actor=request.user,
                )
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Corte actualizado.")
        elif action == "add_expense":
            try:
                add_cash_register_expense(
                    cut=cut, amount=request.POST.get("amount", ""),
                    concept=request.POST.get("concept", ""), actor=request.user,
                )
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Egreso registrado.")
        elif action == "delete_expense":
            CashRegisterExpense.objects.filter(
                pk=request.POST.get("expense_id"), cut=cut,
            ).delete()
            messages.success(request, "Egreso eliminado.")
        return redirect(f"{reverse('cashier:register_cut')}?date={selected_date.isoformat()}")

    # NOTA TEMPORAL PARA APRENDIZAJE: "pendiente de pago" es el mismo criterio
    # que ya usa Cuentas por cobrar, sólo acotado a este día. Borra esta nota.
    unpaid_queryset, pending_queryset = _cash_register_audit_querysets(selected_date)
    unpaid_orders = list(unpaid_queryset.select_related("order", "customer"))

    # NOTA TEMPORAL PARA APRENDIZAJE: "quedó sin resolver" ignora el status tal
    # cual si el pedido ya está registrado como no pagado o cancelado — ambos
    # cuentan como resueltos aunque su status operativo nunca haya llegado a
    # Entregado/Recogido. Lo que sobra son pedidos genuinamente olvidados.
    # Borra esta nota después de leerla.
    pending_orders = list(pending_queryset.order_by("daily_number"))

    expenses = list(cut.expenses.select_related("registered_by"))
    total_expenses = sum((expense.amount for expense in expenses), Decimal("0"))

    hist_from = _report_date(request.GET.get("hist_from"), today - timedelta(days=29))
    hist_to = _report_date(request.GET.get("hist_to"), today)
    if hist_from > hist_to:
        hist_from, hist_to = hist_to, hist_from
    daily_cuts = list(
        CashRegisterCut.objects.filter(operating_date__range=(hist_from, hist_to))
        .prefetch_related("expenses").order_by("-operating_date")
    )
    for daily_cut in daily_cuts:
        daily_cut.total_expenses = sum(
            (expense.amount for expense in daily_cut.expenses.all()), Decimal("0"),
        )

    # NOTA TEMPORAL PARA APRENDIZAJE: la semana corre lunes a domingo (ISO), para
    # que coincida con cómo la mayoría cuenta "esta semana" en México. Sumar
    # opening_cash por semana no tendría sentido (no es un ingreso acumulable),
    # así que el resumen semanal sólo junta ingresos y egresos. Borra esta nota.
    weekly_totals = {}
    for daily_cut in daily_cuts:
        monday = daily_cut.operating_date - timedelta(days=daily_cut.operating_date.weekday())
        bucket = weekly_totals.setdefault(monday, {
            "week_start": monday, "week_end": monday + timedelta(days=6),
            "closing_cash": Decimal("0"), "closing_card": Decimal("0"),
            "closing_transfer": Decimal("0"), "total_income": Decimal("0"),
            "total_expenses": Decimal("0"),
        })
        bucket["closing_cash"] += daily_cut.closing_cash
        bucket["closing_card"] += daily_cut.closing_card
        bucket["closing_transfer"] += daily_cut.closing_transfer
        bucket["total_income"] += daily_cut.total_income
        bucket["total_expenses"] += daily_cut.total_expenses
    weekly_cuts = sorted(weekly_totals.values(), key=lambda week: week["week_start"], reverse=True)

    from tables.models import TableAccount
    parked_table_accounts = list(TableAccount.objects.filter(status=TableAccount.Status.PARKED).select_related("table"))
    return render(request, "orders/cashier_register_cut.html", {
        "parked_table_accounts": parked_table_accounts,
        "cut": cut, "selected_date": selected_date, "today": today,
        "unpaid_orders": unpaid_orders, "pending_orders": pending_orders,
        "expenses": expenses, "total_expenses": total_expenses,
        "daily_cuts": daily_cuts, "weekly_cuts": weekly_cuts,
        "hist_from": hist_from, "hist_to": hist_to,
    })


@role_required(ADMIN)
def cashier_tip_report(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: unificamos dos fuentes sin mezclar su origen.
    # Mesas usa TableAccount y reparto usa Order; ambos terminan en filas equivalentes
    # para filtrar y sumar con la misma regla contable. Borra esta nota al leerla.
    today = timezone.localdate()
    start_date = _report_date(request.GET.get("from"), today)
    end_date = _report_date(request.GET.get("to"), today)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    owner_type = request.GET.get("owner_type", "").strip()
    payment_method = request.GET.get("payment_method", "").strip()
    person_id = request.GET.get("person", "").strip()

    rows = []
    if owner_type in {"", "waiter"}:
        table_tips = TableAccount.objects.filter(
            status=TableAccount.Status.CLOSED, tip_amount__gt=0,
            closed_at__date__range=(start_date, end_date),
        ).select_related("table", "tip_recipient")
        if payment_method in TableAccount.PaymentMethod.values:
            table_tips = table_tips.filter(payment_method=payment_method)
        if person_id.isdigit():
            table_tips = table_tips.filter(tip_recipient_id=int(person_id))
        rows.extend({
            "occurred_at": account.closed_at, "owner_type": "Mesero",
            "owner": account.tip_recipient, "reference": account.table.name,
            "source": "table", "record_id": account.pk,
            "payment_method": account.payment_method,
            "payment_label": account.get_payment_method_display(),
            "amount": account.tip_amount,
            "is_managed": account.payment_method in {TableAccount.PaymentMethod.CARD, TableAccount.PaymentMethod.TRANSFER},
        } for account in table_tips)

    if owner_type in {"", "delivery"} and payment_method != Order.PaymentMethod.CASH:
        delivery_tips = Order.objects.filter(
            order_type=Order.OrderType.DELIVERY, delivery_tip_amount__gt=0,
            delivery_tip_updated_at__date__range=(start_date, end_date),
        ).select_related("delivery_tip_recipient")
        if payment_method in {Order.PaymentMethod.CARD, Order.PaymentMethod.TRANSFER}:
            delivery_tips = delivery_tips.filter(payment_method=payment_method)
        if person_id.isdigit():
            delivery_tips = delivery_tips.filter(delivery_tip_recipient_id=int(person_id))
        rows.extend({
            "occurred_at": order.delivery_tip_updated_at, "owner_type": "Repartidor",
            "owner": order.delivery_tip_recipient, "reference": order.formatted_number,
            "source": "delivery", "record_id": order.pk,
            "payment_method": order.payment_method,
            "payment_label": order.get_payment_method_display(),
            "amount": order.delivery_tip_amount, "is_managed": True,
        } for order in delivery_tips)
    rows.sort(key=lambda row: row["occurred_at"] or timezone.now(), reverse=True)

    methods = (Order.PaymentMethod.CASH, Order.PaymentMethod.CARD, Order.PaymentMethod.TRANSFER)
    totals = {method: sum((row["amount"] for row in rows if row["payment_method"] == method), Decimal("0")) for method in methods}
    managed_total = totals[Order.PaymentMethod.CARD] + totals[Order.PaymentMethod.TRANSFER]
    people = {}
    for row in rows:
        owner = row["owner"]
        key = (row["owner_type"], owner.pk if owner else 0)
        if key not in people:
            people[key] = {
                "owner_type": row["owner_type"], "owner": owner,
                "cash": Decimal("0"), "card": Decimal("0"), "transfer": Decimal("0"),
            }
        people[key][row["payment_method"]] += row["amount"]
    person_totals = list(people.values())
    for person in person_totals:
        person["managed_total"] = person["card"] + person["transfer"]
    person_totals.sort(key=lambda person: (person["owner_type"], (person["owner"].get_full_name() or person["owner"].username) if person["owner"] else ""))
    waiters = get_user_model().objects.filter(groups__name="Mesero").distinct().order_by("first_name", "username")
    couriers = get_user_model().objects.filter(groups__name=DELIVERY).distinct().order_by("first_name", "username")
    return render(request, "orders/cashier_tip_report.html", {
        "rows": rows, "totals": totals, "managed_total": managed_total,
        "person_totals": person_totals,
        "start_date": start_date, "end_date": end_date,
        "selected_owner_type": owner_type, "selected_payment_method": payment_method,
        "selected_person": person_id, "waiters": waiters, "couriers": couriers,
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
    })


@role_required(ADMIN)
def cashier_change_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta bandeja empieza después de Liberar de Caja.
    # Incluye todo efectivo: con cambio o exacto. Caja concilia el dinero total que
    # debe regresar el repartidor, no solamente el cambio matemático.
    # Borra esta nota después de leerla.
    today = timezone.localdate()
    start_date = _report_date(request.GET.get("from"), today)
    end_date = _report_date(request.GET.get("to"), today)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    person_id = request.GET.get("delivery_person", "").strip()
    settlement = request.GET.get("settlement", "pending").strip()
    order_type = request.GET.get("order_type", Order.OrderType.DELIVERY).strip()
    payment_filter = request.GET.get("payment_method", "cash_change").strip()
    status = request.GET.get("status", "").strip()
    search = request.GET.get("q", "").strip()
    exact_folio_query = _full_folio_search_query(search)
    queryset = Order.objects.all()
    if exact_folio_query is not None:
        queryset = queryset.filter(exact_folio_query)
        person_id = ""
        settlement = "all"
        order_type = ""
        payment_filter = "all"
        status = ""
    else:
        queryset = queryset.filter(operating_date__range=(start_date, end_date))
    queryset = queryset.select_related(
        "delivery_person", "cash_settlement_by", "agenda_customer", "customer_debt",
    )
    # NOTA TEMPORAL PARA APRENDIZAJE: cash_change conserva el listado anterior. Los
    # demás medios consultan pedidos finalizados, cuando ya puede saberse que no pagaron.
    # Borra esta nota después de leerla.
    if exact_folio_query is not None:
        pass
    elif payment_filter == "cash_change":
        queryset = queryset.filter(
            order_type=Order.OrderType.DELIVERY,
            payment_method=Order.PaymentMethod.CASH,
            cashier_released_at__isnull=False,
        )
    else:
        queryset = queryset.filter(status__in=(
            Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED, Order.Status.PICKED_UP,
        ))
        if payment_filter in Order.PaymentMethod.values:
            queryset = queryset.filter(payment_method=payment_filter)
        elif payment_filter != "all":
            payment_filter = "cash_change"
            queryset = queryset.filter(
                order_type=Order.OrderType.DELIVERY,
                payment_method=Order.PaymentMethod.CASH,
                cashier_released_at__isnull=False,
            )
        if order_type in Order.OrderType.values:
            queryset = queryset.filter(order_type=order_type)
    if exact_folio_query is None and search:
        queryset = queryset.filter(
            _folio_search_query(search) | Q(customer_name__icontains=search) | Q(phone__icontains=search)
        )
    if exact_folio_query is None and status in Order.Status.values:
        queryset = queryset.filter(status=status)
    queryset = queryset.order_by(
        "cash_settlement_confirmed", "delivery_person__username", "cashier_released_at", "created_at",
    )
    if exact_folio_query is None and person_id.isdigit():
        queryset = queryset.filter(delivery_person_id=int(person_id))
    # El resumen debe representar todo el periodo y repartidor seleccionados. El
    # filtro Pendientes/Devueltos sólo decide qué renglones se ven debajo; si se
    # aplicara antes de sumar, la tarjeta de la categoría contraria siempre daría 0.
    summary_orders = list(queryset) if payment_filter == "cash_change" else []
    if payment_filter == "cash_change":
        if settlement == "pending":
            queryset = queryset.filter(cash_settlement_confirmed=False)
        elif settlement == "settled":
            queryset = queryset.filter(cash_settlement_confirmed=True)
    orders = list(queryset)
    for order in orders:
        order.show_cash_settlement_action = (
            payment_filter == "cash_change"
            or (
                exact_folio_query is not None
                and order.order_type == Order.OrderType.DELIVERY
                and order.payment_method == Order.PaymentMethod.CASH
                and order.cashier_released_at is not None
            )
        )
    today_search_options = [
        {"folio": order.formatted_number, "customer": order.customer_name or "Sin nombre"}
        for order in Order.objects.filter(operating_date=today).order_by("-daily_number")
    ]
    person_totals = {}
    for order in summary_orders:
        key = order.delivery_person_id or 0
        if key not in person_totals:
            person_totals[key] = {"person": order.delivery_person, "pending": Decimal("0"), "settled": Decimal("0")}
        bucket = "settled" if order.cash_settlement_confirmed else "pending"
        person_totals[key][bucket] += order.courier_return_amount or Decimal("0")
    repartidores = get_user_model().objects.filter(groups__name=DELIVERY).distinct().order_by("first_name", "username")
    return render(request, "orders/cashier_change_board.html", {
        "orders": orders, "repartidores": repartidores,
        "person_totals": list(person_totals.values()),
        "pending_total": sum((order.courier_return_amount or Decimal("0") for order in summary_orders if not order.cash_settlement_confirmed), Decimal("0")),
        "settled_total": sum((order.courier_return_amount or Decimal("0") for order in summary_orders if order.cash_settlement_confirmed), Decimal("0")),
        "start_date": start_date, "end_date": end_date,
        "selected_delivery_person": person_id, "selected_settlement": settlement,
        "selected_order_type": order_type, "selected_payment_method": payment_filter,
        "order_type_choices": Order.OrderType.choices,
        "payment_method_choices": ASSIGNABLE_PAYMENT_METHOD_CHOICES,
        "status_choices": Order.Status.choices, "selected_status": status,
        "search": search, "today_search_options": today_search_options,
    })


def _terminal_expected(date_value, person_id="", payment_method=Order.PaymentMethod.CARD):
    """Return app-side totals without treating reconciliation as new revenue."""
    # NOTA TEMPORAL PARA APRENDIZAJE: el total esperado incluye todo lo realmente
    # cobrado por el medio, aunque algunas ventas no necesiten vínculo individual.
    # Vincular sirve para rastrear propinas; no define el ingreso del día. Borra esta nota.
    table_rows = TableAccount.objects.filter(
        status=TableAccount.Status.CLOSED,
        payment_method=payment_method,
        closed_at__date=date_value,
    ).select_related("table", "tip_recipient")
    order_rows = Order.objects.filter(
        operating_date=date_value,
        payment_method=payment_method,
        status__in=(Order.Status.PICKED_UP, Order.Status.DELIVERED),
        customer_debt__isnull=True,
    ).select_related("delivery_tip_recipient")
    debt_payments = CustomerDebtMovement.objects.filter(
        action=CustomerDebtMovement.Action.PAYMENT,
        payment_method=payment_method,
        created_at__date=date_value,
    )
    if person_id.isdigit():
        table_rows = table_rows.filter(tip_recipient_id=int(person_id))
        order_rows = order_rows.filter(delivery_tip_recipient_id=int(person_id))
    table_tip = sum((row.tip_amount for row in table_rows), Decimal("0"))
    order_tip = sum((row.delivery_tip_amount for row in order_rows), Decimal("0"))
    # El total cobrado sólo tiene sentido sin filtro personal: cobros sin propina no
    # pertenecen a un empleado. La propina sí puede conciliarse por persona.
    total = None if person_id else (
        sum(((row.total_paid or Decimal("0")) for row in table_rows), Decimal("0"))
        + sum((row.total_with_delivery_tip for row in order_rows), Decimal("0"))
        + sum((row.amount for row in debt_payments), Decimal("0"))
    )
    return {"total": total, "tip": table_tip + order_tip}


@role_required(ADMIN)
def cashier_terminal_board(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: la app no conoce qué proveedor procesó cada
    # venta; por eso Clover/Mercado Pago se capturan separados, pero la coincidencia
    # autoritativa se calcula sumando ambas terminales contra la app. Borra esta nota.
    selected_date = _report_date(request.GET.get("date"), timezone.localdate())
    reconciliation_view = "reconciliation"
    provider = request.GET.get("provider", TerminalCut.Provider.CLOVER)
    if provider not in (*TerminalCut.Provider.values, reconciliation_view):
        provider = TerminalCut.Provider.CLOVER
    person_id = request.GET.get("person", "").strip()
    employees = list(get_user_model().objects.filter(
        is_active=True, groups__name__in=(WAITER, DELIVERY),
    ).distinct().order_by("first_name", "username"))
    provider_tabs = [*TerminalCut.Provider.choices, (reconciliation_view, "Conciliación")]
    cuts = {}
    for value, _label in TerminalCut.Provider.choices:
        cuts[value], _ = TerminalCut.objects.get_or_create(operating_date=selected_date, provider=value)
    if provider == reconciliation_view:
        reconciliation_movements = TerminalMovement.objects.filter(
            cut__operating_date=selected_date,
        ).select_related("tip_recipient", "cut")
        if person_id.isdigit():
            reconciliation_movements = reconciliation_movements.filter(tip_recipient_id=int(person_id))
        earnings = {}
        for movement in reconciliation_movements:
            key = movement.tip_recipient_id or 0
            if key not in earnings:
                earnings[key] = {
                    "person": movement.tip_recipient,
                    "clover": Decimal("0"), "mercado_pago": Decimal("0"),
                    "transfer": Decimal("0"), "total": Decimal("0"),
                }
            earnings[key][movement.cut.provider] += movement.tip_amount
            earnings[key]["total"] += movement.tip_amount
        reconciliation_rows = sorted(
            earnings.values(),
            key=lambda row: (
                (row["person"].get_full_name() or row["person"].username).casefold()
                if row["person"] else "zzz"
            ),
        )
        return render(request, "orders/cashier_terminal_board.html", {
            "is_reconciliation_view": True,
            "provider_tabs": provider_tabs,
            "provider_choices": TerminalCut.Provider.choices,
            "selected_provider": provider, "selected_date": selected_date,
            "selected_person": person_id, "employees": employees,
            "reconciliation_rows": reconciliation_rows,
            "reconciliation_totals": {
                value: sum((row[value] for row in reconciliation_rows), Decimal("0"))
                for value in ("clover", "mercado_pago", "transfer", "total")
            },
        })
    cut = cuts[provider]
    is_transfer_provider = provider == TerminalCut.Provider.TRANSFER
    is_clover_provider = provider == TerminalCut.Provider.CLOVER
    is_mercado_pago_provider = provider == TerminalCut.Provider.MERCADO_PAGO
    expected_payment_method = (
        Order.PaymentMethod.TRANSFER if is_transfer_provider else Order.PaymentMethod.CARD
    )
    reconciliation_providers = (
        (TerminalCut.Provider.TRANSFER,)
        if is_transfer_provider
        else (TerminalCut.Provider.CLOVER, TerminalCut.Provider.MERCADO_PAGO)
    )
    movements = cut.movements.select_related("tip_recipient", "order", "table_account__table")
    if person_id.isdigit():
        movements = movements.filter(tip_recipient_id=int(person_id))
    movements = list(movements)
    palette_labels = [person.get_full_name() or person.username for person in employees]
    known_palette_labels = {label.casefold() for label in palette_labels}
    manual_references = TerminalMovement.objects.filter(
        cut__operating_date=selected_date,
    ).exclude(terminal_name_reference="").order_by("created_at", "id").values_list(
        "terminal_name_reference", flat=True,
    )
    for reference in manual_references:
        normalized = reference.casefold()
        if normalized not in known_palette_labels:
            known_palette_labels.add(normalized)
            palette_labels.append(reference)
    color_palette = [
        {"label": label, "color": f"hsl({(index * 137 + 12) % 360} 68% 48%)"}
        for index, label in enumerate(palette_labels)
    ]
    combined = TerminalMovement.objects.filter(
        cut__operating_date=selected_date,
        cut__provider__in=reconciliation_providers,
    )
    if person_id.isdigit():
        combined = combined.filter(tip_recipient_id=int(person_id))
    combined = list(combined)
    actual_total = None if person_id else sum((row.total_amount for row in combined), Decimal("0"))
    actual_tip = sum((row.tip_amount for row in combined), Decimal("0"))
    expected = _terminal_expected(selected_date, person_id, expected_payment_method)
    person_summary = []
    for person in employees:
        expected_person = _terminal_expected(
            selected_date, str(person.pk), expected_payment_method,
        )["tip"]
        actual_person = sum((row.tip_amount for row in combined if row.tip_recipient_id == person.pk), Decimal("0")) if not person_id else actual_tip
        if person_id and person.pk != int(person_id):
            continue
        person_summary.append({
            "person": person, "actual": actual_person, "expected": expected_person,
            "difference": actual_person - expected_person,
        })
    # NOTA TEMPORAL PARA APRENDIZAJE: cada tipo de corte ahora vincula un tipo de
    # registro distinto (Clover sólo Mesas, Mercado Pago sólo Entregas, Transferencias
    # ambos) — ver CODEX_CONTEXT.md para las reglas confirmadas. Borra esta nota.
    linked_orders = Order.objects.none()
    if not is_clover_provider:
        order_status_options = (
            (Order.Status.DELIVERED, Order.Status.OUT_FOR_DELIVERY)
            if is_transfer_provider
            else (Order.Status.DELIVERED,)
        )
        # NOTA TEMPORAL PARA APRENDIZAJE: este corte existe para conciliar
        # propinas — un pedido sin propina no tiene nada que vincular aquí, así
        # que se excluye directo de la lista de candidatos (no sólo de la
        # pantalla). El desarrollador lo pidió después de ver tickets con
        # propina $0 apareciendo como vinculables. Borra esta nota.
        linked_orders = Order.objects.filter(
            operating_date=selected_date,
            order_type=Order.OrderType.DELIVERY,
            payment_method=expected_payment_method,
            status__in=order_status_options,
            customer_debt__isnull=True,
            delivery_tip_amount__gt=0,
        ).select_related(
            "delivery_tip_recipient", "delivery_person",
        ).order_by("daily_number")
    linked_tables = TableAccount.objects.none()
    if not is_mercado_pago_provider:
        table_payment_method = (
            TableAccount.PaymentMethod.TRANSFER if is_transfer_provider else TableAccount.PaymentMethod.CARD
        )
        linked_tables = TableAccount.objects.filter(
            status=TableAccount.Status.CLOSED,
            payment_method=table_payment_method,
            closed_at__date=selected_date,
            tip_amount__gt=0,
        ).select_related("table", "tip_recipient", "assigned_waiter").order_by("closed_at")
    used_order_links = dict(TerminalMovement.objects.filter(
        order_id__in=linked_orders.values("id"), order_id__isnull=False,
    ).values_list("order_id", "id"))
    used_table_links = dict(TerminalMovement.objects.filter(
        table_account_id__in=linked_tables.values("id"), table_account_id__isnull=False,
    ).values_list("table_account_id", "id"))
    link_candidates = [{
        "kind": "order", "value": f"order:{row.id}", "label": f"{row.formatted_number} · {row.customer_name}",
        "total": row.total_with_delivery_tip, "tip": row.delivery_tip_amount,
        "recipient_id": row.delivery_tip_recipient_id or row.delivery_person_id or "",
        "movement_id": used_order_links.get(row.id),
    } for row in linked_orders] + [{
        "kind": "table", "value": f"table:{row.id}", "label": f"{row.table.name} · ${row.total_paid}",
        "total": row.total_paid or Decimal("0"), "tip": row.tip_amount,
        "recipient_id": row.tip_recipient_id or row.assigned_waiter_id or "",
        "movement_id": used_table_links.get(row.id),
    } for row in linked_tables]
    # NOTA TEMPORAL PARA APRENDIZAJE: ya no filtramos "disponibles" por renglón en el
    # servidor — se manda la lista completa (con su movement_id, si ya está vinculado a
    # alguno) al frontend vía json_script, y el diálogo de "Vincular" hace el filtro ahí
    # mismo al abrirse, comparando contra el vínculo actual de cada renglón en pantalla.
    # Así no hace falta recargar la página para que un vínculo recién usado desaparezca
    # de los demás renglones. Borra esta nota después de leerla.
    return render(request, "orders/cashier_terminal_board.html", {
        "cut": cut, "cuts": cuts, "movements": movements,
        "provider_tabs": provider_tabs,
        "provider_choices": TerminalCut.Provider.choices,
        "status_choices": TerminalCut.Status.choices,
        "selected_provider": provider, "selected_date": selected_date,
        "is_transfer_provider": is_transfer_provider,
        "reconciliation_label": "Transferencias" if is_transfer_provider else "Clover + Mercado Pago",
        "expected_payment_label": "Transferencia" if is_transfer_provider else "Terminal",
        "selected_person": person_id,
        "employees": employees, "link_candidates": link_candidates,
        "color_palette": color_palette,
        "selected_total": sum((row.total_amount for row in movements), Decimal("0")),
        "selected_tip": sum((row.tip_amount for row in movements), Decimal("0")),
        "actual_total": actual_total, "actual_tip": actual_tip,
        "expected_total": expected["total"], "expected_tip": expected["tip"],
        "total_difference": None if person_id else actual_total - expected["total"],
        "tip_difference": actual_tip - expected["tip"], "person_summary": person_summary,
    })


def _terminal_movement_payload(movement):
    recipient = movement.tip_recipient
    return {
        "id": movement.pk, "total": f"{movement.total_amount:.2f}",
        "tip": f"{movement.tip_amount:.2f}",
        "consumption": f"{movement.consumption_amount:.2f}",
        "recipient_id": movement.tip_recipient_id or "",
        "recipient": (recipient.get_full_name() or recipient.username) if recipient else "Sin asignar",
        "classification_color": movement.classification_color,
    }


@require_POST
@role_required(ADMIN)
@transaction.atomic
def cashier_terminal_movement_save(request):
    cut = get_object_or_404(TerminalCut.objects.select_for_update(), pk=request.POST.get("cut_id"))
    if cut.status == TerminalCut.Status.CLOSED:
        return JsonResponse({"ok": False, "error": "Reabre el corte antes de modificarlo."}, status=400)
    movement_id = request.POST.get("movement_id", "")
    is_new_movement = not movement_id
    movement = get_object_or_404(TerminalMovement, pk=movement_id, cut=cut) if movement_id else TerminalMovement(
        cut=cut, created_by=request.user, display_position=1,
    )
    try:
        total = Decimal(request.POST.get("total_amount", "0"))
        tip = Decimal(request.POST.get("tip_amount", "0") or "0")
    except Exception:
        return JsonResponse({"ok": False, "error": "Escribe importes válidos."}, status=400)
    if total <= 0 or tip < 0 or tip > total:
        return JsonResponse({"ok": False, "error": "El total debe ser mayor a cero y la propina no puede superarlo."}, status=400)
    recipient_id = request.POST.get("tip_recipient", "").strip()
    recipient = None
    if recipient_id:
        recipient = get_user_model().objects.filter(
            is_active=True, groups__name__in=(WAITER, DELIVERY), pk=recipient_id,
        ).distinct().first()
        if recipient is None:
            return JsonResponse({"ok": False, "error": "La persona seleccionada ya no está disponible."}, status=400)
    # La propina puede quedar temporalmente sin asignar: esto permite vincular y
    # autocompletar primero, y seleccionar a la persona en el siguiente toque.
    movement.total_amount = total
    movement.tip_amount = tip
    movement.tip_recipient = recipient
    movement.terminal_name_reference = request.POST.get("terminal_name_reference", "").strip()[:150]
    classification_color = request.POST.get("classification_color", "").strip()
    if classification_color and not re.fullmatch(
        r"hsl\((?:[0-9]|[1-9][0-9]|[12][0-9]{2}|3[0-5][0-9]) 68% 48%\)",
        classification_color,
    ):
        return JsonResponse({"ok": False, "error": "Selecciona un color válido de la paleta."}, status=400)
    movement.classification_color = classification_color
    movement.order = None
    movement.table_account = None
    link = request.POST.get("linked_record", "")
    if link.startswith("order:") and link[6:].isdigit():
        if cut.provider == TerminalCut.Provider.CLOVER:
            return JsonResponse({"ok": False, "error": "Clover sólo admite vincular Mesas."}, status=400)
        linked_order = Order.objects.filter(pk=int(link[6:])).first()
        expected_method = (
            Order.PaymentMethod.TRANSFER
            if cut.provider == TerminalCut.Provider.TRANSFER
            else Order.PaymentMethod.CARD
        )
        allowed_statuses = (
            (Order.Status.DELIVERED, Order.Status.OUT_FOR_DELIVERY)
            if cut.provider == TerminalCut.Provider.TRANSFER
            else (Order.Status.DELIVERED,)
        )
        if (
            not linked_order
            or linked_order.order_type != Order.OrderType.DELIVERY
            or linked_order.payment_method != expected_method
            or linked_order.status not in allowed_statuses
        ):
            return JsonResponse({"ok": False, "error": "Ese pedido no corresponde al tipo de cobro de este apartado."}, status=400)
        if TerminalMovement.objects.filter(order=linked_order).exclude(pk=movement.pk).exists():
            return JsonResponse({
                "ok": False, "code": "link_already_used",
                "error": "Ese pedido acaba de vincularse en otro movimiento. Selecciona otro.",
            }, status=409)
        movement.order = linked_order
    elif link.startswith("table:") and link[6:].isdigit():
        if cut.provider == TerminalCut.Provider.MERCADO_PAGO:
            return JsonResponse({"ok": False, "error": "Mercado Pago sólo admite vincular pedidos de Entrega."}, status=400)
        expected_table_method = (
            TableAccount.PaymentMethod.TRANSFER
            if cut.provider == TerminalCut.Provider.TRANSFER
            else TableAccount.PaymentMethod.CARD
        )
        linked_table = TableAccount.objects.filter(pk=int(link[6:])).first()
        if (
            not linked_table
            or linked_table.status != TableAccount.Status.CLOSED
            or linked_table.payment_method != expected_table_method
        ):
            return JsonResponse({"ok": False, "error": "Esa mesa no corresponde al tipo de cobro de este apartado."}, status=400)
        if TerminalMovement.objects.filter(table_account=linked_table).exclude(pk=movement.pk).exists():
            return JsonResponse({
                "ok": False, "code": "link_already_used",
                "error": "Esa mesa acaba de vincularse en otro movimiento. Selecciona otra.",
            }, status=409)
        movement.table_account = linked_table
    if is_new_movement:
        # NOTA TEMPORAL PARA APRENDIZAJE: la captura vacía vive arriba; por eso el
        # movimiento nuevo ocupa siempre la primera posición y empuja hacia abajo a
        # los anteriores. También normaliza registros viejos que todavía tenían 0.
        # Borra esta nota después de leerla.
        previous_movements = list(cut.movements.select_for_update())
        for position, previous in enumerate(previous_movements, start=2):
            previous.display_position = position
        TerminalMovement.objects.bulk_update(previous_movements, ("display_position",))
    movement.save()
    return JsonResponse({"ok": True, "movement": _terminal_movement_payload(movement)})


@require_POST
@role_required(ADMIN)
@transaction.atomic
def cashier_terminal_movement_reorder(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: el navegador manda sólo las filas visibles,
    # que pueden estar filtradas por persona. Sustituimos esas filas dentro de sus
    # posiciones actuales y dejamos intactas las filas ocultas por el filtro.
    # Borra esta nota después de leerla.
    cut = get_object_or_404(TerminalCut.objects.select_for_update(), pk=request.POST.get("cut_id"))
    if cut.status == TerminalCut.Status.CLOSED:
        return JsonResponse({"ok": False, "error": "Reabre el corte antes de reordenar movimientos."}, status=400)
    raw_ids = request.POST.getlist("movement_ids[]") or request.POST.getlist("movement_ids")
    if not raw_ids or any(not value.isdigit() for value in raw_ids):
        return JsonResponse({"ok": False, "error": "El orden enviado no es válido."}, status=400)
    movement_ids = [int(value) for value in raw_ids]
    if len(movement_ids) != len(set(movement_ids)):
        return JsonResponse({"ok": False, "error": "El orden contiene registros repetidos."}, status=400)
    movements = list(cut.movements.select_for_update())
    by_id = {movement.pk: movement for movement in movements}
    if any(movement_id not in by_id for movement_id in movement_ids):
        return JsonResponse({"ok": False, "error": "Una fila ya no pertenece a este corte."}, status=400)
    visible_ids = set(movement_ids)
    visible_slots = [index for index, movement in enumerate(movements) if movement.pk in visible_ids]
    reordered = list(movements)
    for slot, movement_id in zip(visible_slots, movement_ids):
        reordered[slot] = by_id[movement_id]
    for position, movement in enumerate(reordered, start=1):
        movement.display_position = position
    TerminalMovement.objects.bulk_update(reordered, ("display_position",))
    return JsonResponse({"ok": True, "movement_ids": movement_ids})


@require_POST
@role_required(ADMIN)
def cashier_terminal_movement_delete(request, movement_id):
    movement = get_object_or_404(TerminalMovement.objects.select_related("cut"), pk=movement_id)
    if movement.cut.status == TerminalCut.Status.CLOSED:
        return JsonResponse({"ok": False, "error": "Reabre el corte antes de eliminar movimientos."}, status=400)
    movement.delete()
    return JsonResponse({"ok": True})


@require_POST
@role_required(ADMIN)
def cashier_terminal_cut_status(request, cut_id):
    cut = get_object_or_404(TerminalCut, pk=cut_id)
    close = request.POST.get("status") == TerminalCut.Status.CLOSED
    cut.status = TerminalCut.Status.CLOSED if close else TerminalCut.Status.OPEN
    cut.closed_at = timezone.now() if close else None
    cut.closed_by = request.user if close else None
    cut.save(update_fields=("status", "closed_at", "closed_by", "updated_at"))
    return JsonResponse({"ok": True, "status": cut.status, "status_label": cut.get_status_display()})


@role_required(ADMIN)
def cashier_tip_detail(request, source, record_id):
    # NOTA TEMPORAL PARA APRENDIZAJE: este endpoint devuelve sólo los datos del ticket
    # solicitado. Así el reporte inicial no descarga cientos de partidas que quizá nunca
    # se abrirán. Borra esta nota después de leerla.
    if source == "table":
        account = get_object_or_404(
            TableAccount.objects.select_related("table", "assigned_waiter", "tip_recipient", "closed_by").prefetch_related("items"),
            pk=record_id,
        )
        items = [{
            "name": item.product_name_snapshot or item.package_name_snapshot,
            "quantity": item.quantity, "subtotal": f"{item.subtotal:.2f}",
            "comment": item.customization_comment,
            "description": " · ".join(filter(None, (
                item.first_course_snapshot, item.second_course_snapshot,
                item.main_course_snapshot,
            ))),
        } for item in account.items.all()]
        return JsonResponse({"ok": True, "detail": {
            "kind": "Mesa", "reference": account.table.name,
            "customer": account.customer_name or "Sin nombre",
            "responsible_label": "Mesero", "responsible": (
                (account.tip_recipient.get_full_name() or account.tip_recipient.username)
                if account.tip_recipient else "Sin asignar"
            ),
            "date": timezone.localtime(account.closed_at).strftime("%d/%m/%Y %H:%M") if account.closed_at else "",
            "payment": account.get_payment_method_display(), "consumption": f"{account.subtotal_closed or 0:.2f}",
            "tip": f"{account.tip_amount:.2f}", "total": f"{account.total_paid or 0:.2f}",
            "address": "Consumo en mesa", "notes": "", "items": items,
        }})
    if source == "delivery":
        order = get_object_or_404(
            Order.objects.select_related("delivery_tip_recipient", "delivery_person").prefetch_related("items"),
            pk=record_id, order_type=Order.OrderType.DELIVERY,
        )
        items = [{
            "name": item.product_name_snapshot or item.package_name_snapshot,
            "quantity": item.quantity, "subtotal": f"{item.subtotal:.2f}",
            "comment": item.customization_comment,
            "description": " · ".join(filter(None, (
                item.first_course_name_snapshot, item.second_course_name_snapshot,
                item.main_course_name_snapshot,
            ))),
        } for item in order.items.all()]
        recipient = order.delivery_tip_recipient or order.delivery_person
        return JsonResponse({"ok": True, "detail": {
            "kind": "Entrega a domicilio", "reference": order.formatted_number,
            "customer": order.customer_name or "Sin nombre",
            "responsible_label": "Repartidor", "responsible": (
                (recipient.get_full_name() or recipient.username) if recipient else "Sin asignar"
            ),
            "date": timezone.localtime(order.delivery_tip_updated_at).strftime("%d/%m/%Y %H:%M") if order.delivery_tip_updated_at else "",
            "payment": order.get_payment_method_display(), "consumption": f"{order.total:.2f}",
            "tip": f"{order.delivery_tip_amount:.2f}", "total": f"{order.total_with_delivery_tip:.2f}",
            "address": " ".join(filter(None, (order.street, order.exterior_number, order.interior_number, order.neighborhood))),
            "notes": order.notes, "items": items,
        }})
    return JsonResponse({"ok": False, "error": "Tipo de propina no reconocido."}, status=404)


@require_POST
@role_required(ADMIN, ORDER_TAKER, WAITER)
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
def cashier_cash_settlement(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = confirm_cash_settlement(
            order=order, actor=request.user,
            confirmed=request.POST.get("confirmed", "1") == "1",
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({"ok": True, **_cashier_order_payload(order)})


@require_POST
@role_required(ADMIN)
def cashier_release_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    try:
        order = set_cashier_release(
            order=order, actor=request.user,
            released=request.POST.get("released", "1") == "1",
        )
    except ValidationError as error:
        return JsonResponse({"ok": False, "error": error.message}, status=400)
    return JsonResponse({
        "ok": True, "released": order.cashier_released_at is not None,
        "message": f"{order.formatted_number} fue liberado de Caja.",
    })
