from django.db import transaction
from django.utils import timezone

from .models import StockAlert


@transaction.atomic
def sync_stock_alert(stock):
    """Open or resolve the current low-stock alert for one inventory bucket."""
    available = stock.available_quantity
    active = StockAlert.objects.select_for_update().filter(stock=stock, is_active=True).first()
    should_alert = stock.is_tracked and stock.initial_quantity > 0 and available <= stock.low_stock_threshold

    if should_alert:
        if active:
            if active.available_quantity != available:
                active.available_quantity = available
                active.save(update_fields=("available_quantity",))
            return active
        alert = StockAlert.objects.create(stock=stock, available_quantity=available)
        return alert

    if active:
        active.is_active = False
        active.resolved_at = timezone.now()
        active.save(update_fields=("is_active", "resolved_at"))
    return None
