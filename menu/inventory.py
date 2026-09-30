from django.core.exceptions import ValidationError
from django.db import transaction

from .models import DailyProductStock, StockMovement


def filter_products_by_stock(products, *, daily_menu, channel):
    """Keep exhausted products sellable; shortages are warnings, not blockers."""
    return list(products)


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
    """Stock is informative: zero quantities no longer block publication."""
    return []


def stock_warning_payload(*, selected_date):
    """Shortages combined across Mesas/Pedidos for the interactive ticket only."""
    rows = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.DAILY,
        date=selected_date,
        is_tracked=True,
    ).select_related("product")
    grouped = {}
    for stock in rows:
        key = (stock.item_kind, stock.product_id, stock.chicken_piece)
        entry = grouped.setdefault(key, {"name": stock.item_name, "available": 0})
        entry["available"] += stock.available_quantity
    return [
        {
            "name": entry["name"],
            "available": entry["available"],
            "shortage": abs(entry["available"]),
            "message": f"Stock rebasado: {entry['name']} ({entry['available']})",
        }
        for entry in grouped.values() if entry["available"] < 0
    ]
