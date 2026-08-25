# NOTA TEMPORAL PARA APRENDIZAJE:
# La asignación de reparto usa bloqueo y valida quién puede cerrar una entrega.
# Centralizamos la máquina de estados y su historial. El backend decide qué acción sigue;
# la plantilla solo muestra esas opciones. Borra esta nota después de leerla.
# El checkout nuevo recorre todas las partidas resueltas y calcula otra vez sus precios.
# También crea o atiende la notificación dentro de la misma transacción del pedido.
# Este servicio guarda encabezado y partida dentro de una sola transacción. Si algo falla,
# no queda medio pedido guardado. También vuelve a leer el precio y genera el folio diario
# con bloqueo para evitar números repetidos. Borra esta nota después de leerla.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, user_has_any_role
from menu.models import DailyMenu, MealPackage
from notifications.models import InternalNotification

from .models import DailyOrderCounter, Order, OrderItem, OrderStatusHistory


ACTION_LABELS = {
    "confirm": "Confirmar pedido",
    "cancel": "Cancelar pedido",
    "start_preparing": "Iniciar preparación",
    "mark_ready": "Marcar como listo",
    "complete_pickup": "Marcar como recogido",
    "complete_delivery": "Marcar como entregado",
    "restart_cycle": "Iniciar nuevo ciclo",
}


def available_order_actions(order):
    if order.status == Order.Status.PENDING_CONFIRMATION:
        return ("confirm", "cancel")
    if order.status == Order.Status.CONFIRMED:
        return ("start_preparing",)
    if order.status == Order.Status.PREPARING:
        return ("mark_ready",)
    if order.status == Order.Status.READY and order.order_type == Order.OrderType.PICKUP:
        return ("complete_pickup",)
    if order.status in {Order.Status.PICKED_UP, Order.Status.DELIVERED}:
        return ("restart_cycle",)
    return ()


@transaction.atomic
def create_public_cart_order(*, cart_data, cleaned_data):
    if not cart_data["items"]:
        raise ValidationError("El carrito está vacío.")
    total = sum((item["subtotal"] for item in cart_data["items"]), start=0)
    if cleaned_data["cash_tendered"] is not None and cleaned_data["cash_tendered"] < total:
        raise ValidationError("La cantidad en efectivo no cubre el total actualizado.")

    today = timezone.localdate()
    counter, _ = DailyOrderCounter.objects.select_for_update().get_or_create(operating_date=today)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    order_type = cleaned_data["order_type"]
    order = Order.objects.create(
        daily_number=counter.last_number,
        operating_date=today,
        order_type=order_type,
        customer_name=" ".join(filter(None, (
            cleaned_data["customer_first_name"].strip(), cleaned_data["customer_last_name"].strip(),
        ))),
        phone=cleaned_data["phone"].strip(),
        street=cleaned_data["street"].strip() if order_type == Order.OrderType.DELIVERY else "",
        exterior_number=cleaned_data["exterior_number"].strip() if order_type == Order.OrderType.DELIVERY else "",
        interior_number=cleaned_data["interior_number"].strip() if order_type == Order.OrderType.DELIVERY else "",
        neighborhood=cleaned_data["neighborhood"].strip() if order_type == Order.OrderType.DELIVERY else "",
        references=cleaned_data["references"].strip() if order_type == Order.OrderType.DELIVERY else "",
        notes=cleaned_data["notes"].strip(),
        payment_method=cleaned_data["payment_method"],
        needs_change=cleaned_data["needs_change"],
        cash_tendered=cleaned_data["cash_tendered"],
        total=total,
    )
    OrderStatusHistory.objects.create(
        order=order, from_status="", to_status=Order.Status.PENDING_CONFIRMATION
    )
    for item in cart_data["items"]:
        if item["kind"] == "product":
            product = item["product"]
            OrderItem.objects.create(
                order=order, item_type=OrderItem.ItemType.PRODUCT, product=product,
                product_name_snapshot=product.name, unit_price=item["unit_price"],
                quantity=item["quantity"], subtotal=item["subtotal"],
                tortillas=False, beans=False,
            )
        else:
            OrderItem.objects.create(
                order=order, item_type=OrderItem.ItemType.PACKAGE, package=item["package"],
                package_name_snapshot=item["package"].name,
                first_course=item["first_course"], first_course_name_snapshot=item["first_course"].name,
                second_course=item["second_course"], second_course_name_snapshot=item["second_course"].name,
                main_course=item["main_course"], main_course_name_snapshot=item["main_course"].name,
                chicken_piece=item["chicken_piece"], with_water=item["with_water"],
                water_name_snapshot=item["daily_menu"].water_product.name if item["with_water"] else "",
                tortillas=item["tortillas"], beans=item["beans"], unit_price=item["unit_price"],
                quantity=item["quantity"], subtotal=item["subtotal"],
            )
    InternalNotification.objects.create(
        notification_type=InternalNotification.NotificationType.NEW_PUBLIC_ORDER,
        order=order,
        title=f"Nuevo pedido web {order.formatted_number}",
        message=f"{order.customer_name} · {order.get_order_type_display()} · ${order.total}",
    )
    return order


@transaction.atomic
def create_public_package_order(*, package, daily_menu, cleaned_data):
    package = MealPackage.objects.select_for_update().get(pk=package.pk, is_active=True)
    daily_menu = DailyMenu.objects.select_for_update().get(
        pk=daily_menu.pk, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED
    )
    total = package.price_with_water if cleaned_data["with_water"] else package.price_without_water
    if cleaned_data["cash_tendered"] is not None and cleaned_data["cash_tendered"] < total:
        raise ValidationError("La cantidad en efectivo ya no cubre el total actualizado.")

    today = timezone.localdate()
    counter, _ = DailyOrderCounter.objects.select_for_update().get_or_create(operating_date=today)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])

    order = Order.objects.create(
        daily_number=counter.last_number,
        operating_date=today,
        order_type=cleaned_data["order_type"],
        customer_name=" ".join(filter(None, (
            cleaned_data["customer_first_name"].strip(),
            cleaned_data["customer_last_name"].strip(),
        ))),
        phone=cleaned_data["phone"].strip(),
        street=cleaned_data["street"].strip() if cleaned_data["order_type"] == Order.OrderType.DELIVERY else "",
        exterior_number=cleaned_data["exterior_number"].strip() if cleaned_data["order_type"] == Order.OrderType.DELIVERY else "",
        interior_number=cleaned_data["interior_number"].strip() if cleaned_data["order_type"] == Order.OrderType.DELIVERY else "",
        neighborhood=cleaned_data["neighborhood"].strip() if cleaned_data["order_type"] == Order.OrderType.DELIVERY else "",
        references=cleaned_data["references"].strip() if cleaned_data["order_type"] == Order.OrderType.DELIVERY else "",
        notes=cleaned_data["notes"].strip(),
        payment_method=cleaned_data["payment_method"],
        needs_change=cleaned_data["needs_change"],
        cash_tendered=cleaned_data["cash_tendered"],
        total=total,
    )
    first_course = cleaned_data["first_course"]
    second_course = cleaned_data["second_course"]
    main_course = cleaned_data["main_course"]
    OrderItem.objects.create(
        order=order,
        package=package,
        package_name_snapshot=package.name,
        first_course=first_course,
        first_course_name_snapshot=first_course.name,
        second_course=second_course,
        second_course_name_snapshot=second_course.name,
        main_course=main_course,
        main_course_name_snapshot=main_course.name,
        chicken_piece=cleaned_data["chicken_piece"],
        with_water=cleaned_data["with_water"],
        water_name_snapshot=daily_menu.water_product.name if cleaned_data["with_water"] else "",
        tortillas=cleaned_data["tortillas"] == "yes",
        beans=cleaned_data["beans"] == "yes",
        unit_price=total,
        subtotal=total,
    )
    return order


@transaction.atomic
def transition_order(*, order, action, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    transitions = {
        (Order.Status.PENDING_CONFIRMATION, "confirm"): Order.Status.CONFIRMED,
        (Order.Status.PENDING_CONFIRMATION, "cancel"): Order.Status.CANCELED,
        (Order.Status.CONFIRMED, "start_preparing"): Order.Status.PREPARING,
        (Order.Status.PREPARING, "mark_ready"): Order.Status.READY,
        (Order.Status.READY, "complete_pickup"): Order.Status.PICKED_UP,
        (Order.Status.READY, "complete_delivery"): Order.Status.DELIVERED,
        (Order.Status.PICKED_UP, "restart_cycle"): Order.Status.PENDING_CONFIRMATION,
        (Order.Status.DELIVERED, "restart_cycle"): Order.Status.PENDING_CONFIRMATION,
    }
    target_status = transitions.get((order.status, action))
    if not target_status:
        raise ValidationError("Ese cambio no está permitido desde el estado actual.")
    if action == "complete_pickup" and order.order_type != Order.OrderType.PICKUP:
        raise ValidationError("Solo un pedido para recoger puede marcarse como recogido.")
    if action == "complete_delivery" and order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("Solo un pedido de entrega puede marcarse como entregado.")
    if action == "complete_delivery":
        if order.delivery_person_id is None:
            raise ValidationError("Primero debes asignar el pedido a un repartidor.")
        can_complete = actor == order.delivery_person or user_has_any_role(
            actor, (ADMIN, ORDER_TAKER)
        )
        if not can_complete:
            raise ValidationError("Solo el repartidor asignado puede completar esta entrega.")
    if order.attention_started_at is None and actor is not None:
        order.attention_started_at = timezone.now()
        order.attention_started_by = actor
    previous_status = order.status
    order.status = target_status
    update_fields = ["status", "updated_at"]
    if action == "restart_cycle":
        order.delivery_person = None
        order.delivery_assigned_by = None
        order.delivery_assigned_at = None
        update_fields.extend([
            "delivery_person", "delivery_assigned_by", "delivery_assigned_at",
        ])
    if "attention_started_at" in order.__dict__ and order.attention_started_at:
        update_fields.extend(["attention_started_at", "attention_started_by"])
    order.save(update_fields=update_fields)
    OrderStatusHistory.objects.create(
        order=order, from_status=previous_status, to_status=target_status, changed_by=actor
    )
    InternalNotification.objects.filter(order=order, is_read=False).update(
        is_read=True, read_at=timezone.now(), read_by=actor
    )
    return order


@transaction.atomic
def assign_delivery(*, order, delivery_person, assigned_by):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("Los pedidos para recoger no se asignan a repartidores.")
    if not delivery_person.is_active or not delivery_person.groups.filter(name=DELIVERY).exists():
        raise ValidationError("Selecciona un usuario activo con rol Repartidor.")
    order.delivery_person = delivery_person
    order.delivery_assigned_by = assigned_by
    order.delivery_assigned_at = timezone.now()
    order.save(update_fields=[
        "delivery_person", "delivery_assigned_by", "delivery_assigned_at", "updated_at",
    ])
    return order
