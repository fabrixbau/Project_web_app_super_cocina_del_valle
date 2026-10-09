"""Eliminar productos del menú aunque tengan historial (decisión del dueño, 2026-10-09).

Sólo se bloquea si el producto está en un menú del día publicado y activo (hoy o una fecha
futura) y ya tiene piezas comprometidas (apartadas o vendidas). En cualquier otro caso se
elimina junto con su historial: se quita de los menús del día (el lugar queda vacío o el
guisado sale de la lista) y se borran sus existencias diarias con sus movimientos,
auditorías y alertas. Las ventas (pedidos y cuentas) no se tocan: guardan nombre y precio.
"""

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DailyMenu, DailyMenuStew, DailyProductStock, InventoryAuditLog, StockMovement

MENU_FIELDS = (
    "water_product", "chicken_consomme", "variable_first_course",
    "second_course_one", "second_course_two", "beans_order",
)
COMMITTING_REASONS = (
    StockMovement.Reason.RESERVATION, StockMovement.Reason.RELEASE, StockMovement.Reason.CONSUMPTION,
)


def _menus_with_product(product, queryset):
    from django.db.models import Q

    condition = Q(stew_entries__product=product)
    for field in MENU_FIELDS:
        condition |= Q(**{field: product})
    return queryset.filter(condition).distinct()


def product_delete_blocker(product):
    """Texto del motivo si no se puede eliminar; vacío si sí se puede."""
    active_menus = _menus_with_product(
        product, DailyMenu.objects.filter(status=DailyMenu.Status.PUBLISHED, date__gte=timezone.localdate()),
    )
    for menu in active_menus.order_by("date"):
        net = StockMovement.objects.filter(
            stock__product=product, stock__date=menu.date, reason__in=COMMITTING_REASONS,
        ).aggregate(total=Sum("quantity"))["total"] or 0
        if net < 0:
            return (
                f"está en el menú publicado del {menu.date:%d/%m/%Y} y ya tiene {-net} "
                f"pieza{'s' if -net != 1 else ''} apartada{'s' if -net != 1 else ''} o vendida{'s' if -net != 1 else ''}"
            )
    return ""


def product_delete_impact(product):
    """Qué historial se borrará (para avisar en la confirmación)."""
    stocks = DailyProductStock.objects.filter(product=product)
    return {
        "menus": _menus_with_product(product, DailyMenu.objects.all()).count(),
        "stock_days": stocks.values("date").distinct().count(),
    }


@transaction.atomic
def delete_product_with_history(product):
    for field in MENU_FIELDS:
        DailyMenu.objects.filter(**{field: product}).update(**{field: None})
    DailyMenuStew.objects.filter(product=product).delete()
    stocks = DailyProductStock.objects.filter(product=product)
    StockMovement.objects.filter(stock__in=stocks).delete()
    InventoryAuditLog.objects.filter(stock__in=stocks).delete()
    stocks.delete()  # las alertas de existencia se borran en cascada
    product.delete()
