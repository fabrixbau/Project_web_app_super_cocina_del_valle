# NOTA TEMPORAL PARA APRENDIZAJE:
# Al guardar unimos nombre y apellido en el snapshot customer_name del pedido.
# El checkout nuevo recorre todas las partidas resueltas y calcula otra vez sus precios.
# También crea o atiende la notificación dentro de la misma transacción del pedido.
# Este servicio guarda encabezado y partida dentro de una sola transacción. Si algo falla,
# no queda medio pedido guardado. También vuelve a leer el precio y genera el folio diario
# con bloqueo para evitar números repetidos. Borra esta nota después de leerla.

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from menu.models import DailyMenu, MealPackage
from notifications.models import InternalNotification

from .models import DailyOrderCounter, Order, OrderItem


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
def resolve_pending_order(*, order, action, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.PENDING_CONFIRMATION:
        raise ValidationError("Este pedido ya fue atendido y no puede resolverse otra vez.")
    status_by_action = {
        "confirm": Order.Status.CONFIRMED,
        "cancel": Order.Status.CANCELED,
    }
    if action not in status_by_action:
        raise ValidationError("La acción solicitada no es válida.")
    order.status = status_by_action[action]
    order.save(update_fields=["status", "updated_at"])
    InternalNotification.objects.filter(order=order, is_read=False).update(
        is_read=True, read_at=timezone.now(), read_by=actor
    )
    return order
