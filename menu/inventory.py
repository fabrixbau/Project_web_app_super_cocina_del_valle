from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import DailyProductStock, StockMovement


def filter_products_by_stock(products, *, daily_menu, channel):
    """Hide exhausted tracked products while leaving untracked fixed-menu items alone."""
    products = list(products)
    if not products:
        return products
    product_ids = {product.pk for product in products}
    daily_ids = set()
    if daily_menu:
        daily_ids = {product_id for product_id in (
            daily_menu.water_product_id, daily_menu.chicken_consomme_id,
            daily_menu.variable_first_course_id, daily_menu.second_course_one_id,
            daily_menu.second_course_two_id, daily_menu.chicken_stew_id,
            daily_menu.beef_stew_id, daily_menu.varied_stew_id,
            daily_menu.beans_order_id,
        ) if product_id}
    daily_rows = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.DAILY,
        date=daily_menu.date if daily_menu else None,
        channel=channel, product_id__in=product_ids & daily_ids,
    ) if daily_menu else DailyProductStock.objects.none()
    fixed_rows = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.FIXED,
        channel=DailyProductStock.Channel.SHARED,
        is_tracked=True, product_id__in=product_ids - daily_ids,
    )
    daily_available = {}
    for stock in daily_rows:
        daily_available[stock.product_id] = daily_available.get(stock.product_id, 0) + stock.available_quantity
    fixed_available = {stock.product_id: stock.available_quantity for stock in fixed_rows}
    return [
        product for product in products
        if (
            (product.pk not in daily_ids or daily_available.get(product.pk, 0) > 0)
            and (product.pk in daily_ids or product.pk not in fixed_available or fixed_available[product.pk] > 0)
        )
    ]


@transaction.atomic
def record_stock_movement(
    *,
    stock,
    quantity,
    reason,
    actor,
    reference_type="",
    reference_id=None,
    note="",
):
    """Record an auditable movement while serializing changes to one stock bucket."""
    if not quantity:
        raise ValidationError("El movimiento de inventario no puede ser cero.")

    locked_stock = DailyProductStock.objects.select_for_update().get(pk=stock.pk)
    movement_total = locked_stock.movements.aggregate(total=Sum("quantity"))["total"] or 0
    resulting_quantity = locked_stock.initial_quantity + movement_total + quantity
    if resulting_quantity < 0:
        raise ValidationError(
            f"No hay suficientes raciones de {locked_stock.item_name} para "
            f"{locked_stock.get_channel_display().lower()}. "
            f"Disponibles: {locked_stock.initial_quantity + movement_total}."
        )

    movement = StockMovement.objects.create(
        stock=locked_stock,
        quantity=quantity,
        reason=reason,
        actor=actor,
        reference_type=reference_type,
        reference_id=reference_id,
        note=" ".join(note.split()),
    )
    from notifications.services import sync_stock_alert
    sync_stock_alert(locked_stock)
    return movement


def reserve_stock(*, stock, quantity, actor, reference_type, reference_id, note=""):
    if quantity <= 0:
        raise ValidationError("La cantidad a reservar debe ser mayor que cero.")
    return record_stock_movement(
        stock=stock,
        quantity=-quantity,
        reason=StockMovement.Reason.RESERVATION,
        actor=actor,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )


def release_stock(*, stock, quantity, actor, reference_type, reference_id, note=""):
    if quantity <= 0:
        raise ValidationError("La cantidad a devolver debe ser mayor que cero.")
    return record_stock_movement(
        stock=stock,
        quantity=quantity,
        reason=StockMovement.Reason.RELEASE,
        actor=actor,
        reference_type=reference_type,
        reference_id=reference_id,
        note=note,
    )


def adjust_stock(*, stock, quantity, actor, note):
    if not note or not note.strip():
        raise ValidationError("Explica el motivo del ajuste.")
    return record_stock_movement(
        stock=stock, quantity=quantity, reason=StockMovement.Reason.ADJUSTMENT,
        actor=actor, reference_type="manual_adjustment", note=note,
    )


@transaction.atomic
def transfer_stock(*, source, target, quantity, actor, note):
    if quantity <= 0:
        raise ValidationError("La cantidad a transferir debe ser mayor que cero.")
    if not note or not note.strip():
        raise ValidationError("Explica el motivo de la transferencia.")
    if source.pk == target.pk:
        raise ValidationError("Selecciona dos canales diferentes.")

    locked = {
        stock.pk: stock
        for stock in DailyProductStock.objects.select_for_update()
        .filter(pk__in=(source.pk, target.pk)).order_by("pk")
    }
    source = locked.get(source.pk)
    target = locked.get(target.pk)
    if not source or not target:
        raise ValidationError("Una de las existencias ya no está disponible.")
    identity = lambda stock: (
        stock.date, stock.item_kind, stock.product_id, stock.chicken_piece,
    )
    if identity(source) != identity(target):
        raise ValidationError("Solo puedes transferir el mismo producto o insumo del mismo día.")
    if source.channel == target.channel:
        raise ValidationError("Selecciona dos canales diferentes.")

    clean_note = " ".join(note.split())
    outgoing = record_stock_movement(
        stock=source, quantity=-quantity, reason=StockMovement.Reason.TRANSFER_OUT,
        actor=actor, reference_type="stock_transfer", reference_id=target.pk,
        note=f"Hacia {target.get_channel_display()}: {clean_note}",
    )
    record_stock_movement(
        stock=target, quantity=quantity, reason=StockMovement.Reason.TRANSFER_IN,
        actor=actor, reference_type="stock_transfer", reference_id=source.pk,
        note=f"Desde {source.get_channel_display()}: {clean_note}",
    )
    return outgoing


def daily_menu_stock_errors(daily_menu):
    """Return human-friendly publication errors for incomplete allocations."""
    required_products = [
        product for product in (
            daily_menu.water_product, daily_menu.chicken_consomme,
            daily_menu.variable_first_course, daily_menu.second_course_one,
            daily_menu.second_course_two, daily_menu.chicken_stew,
            daily_menu.beef_stew, daily_menu.varied_stew,
        ) if product
    ]
    stocks = list(daily_menu.product_stocks.all())
    errors = []
    channels = {DailyProductStock.Channel.TABLE, DailyProductStock.Channel.ORDERS}
    for product in required_products:
        rows = [stock for stock in stocks if stock.product_id == product.pk]
        if product.pk == daily_menu.chicken_stew_id:
            for piece, label in DailyProductStock.ChickenPiece.choices:
                piece_rows = [stock for stock in rows if stock.chicken_piece == piece]
                if {row.channel for row in piece_rows} != channels or sum(row.initial_quantity for row in piece_rows) <= 0:
                    errors.append(f"{product.name} · {label}")
        elif {row.channel for row in rows if not row.chicken_piece} != channels or sum(
            row.initial_quantity for row in rows if not row.chicken_piece
        ) <= 0:
            errors.append(product.name)
    for item_kind, label in (
        (DailyProductStock.ItemKind.TORTILLAS, "Tortillas"),
        (DailyProductStock.ItemKind.BREAD, "Bolillos"),
    ):
        rows = [stock for stock in stocks if stock.item_kind == item_kind]
        if {row.channel for row in rows} != channels or sum(row.initial_quantity for row in rows) <= 0:
            errors.append(label)
    return errors
