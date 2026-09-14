from collections import defaultdict
from decimal import Decimal
import unicodedata

from tables.models import TableAccount, TableAccountItem

from .models import Order, OrderItem


def _normalized(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in value if not unicodedata.combining(char)).strip().casefold()


def _option_labels(snapshot):
    if not isinstance(snapshot, dict):
        return set()
    return {
        _normalized(option.get("name"))
        for group in snapshot.get("groups", [])
        if isinstance(group, dict)
        for option in group.get("selected", [])
        if isinstance(option, dict)
    }


def _row(item, source, reference, finalized):
    labels = _option_labels(item.configuration_snapshot)
    size = "Grande" if "grande" in labels else "Mediano"
    milk = "Deslactosada" if "deslactosada" in labels else "Entera" if "entera" in labels else "Sin especificar"
    return {
        "product": item.product_name_snapshot, "size": size, "milk": milk,
        "quantity": item.quantity, "unit_price": item.unit_price, "total": item.subtotal,
        "source": source, "reference": reference, "finalized": finalized,
    }


def coffee_sales_for_date(selected_date):
    rows = []
    orders = OrderItem.objects.filter(
        order__operating_date=selected_date, item_type=OrderItem.ItemType.PRODUCT,
        product__category__name__iexact="Bebidas calientes",
    ).select_related("order")
    for item in orders:
        if item.order.status == Order.Status.CANCELED:
            continue
        finalized = item.order.status in {Order.Status.PICKED_UP, Order.Status.DELIVERED}
        rows.append(_row(item, "Pedido", item.order.formatted_number, finalized))

    table_items = TableAccountItem.objects.filter(
        account__opened_at__date=selected_date, item_type=TableAccountItem.ItemType.PRODUCT,
        product__category__name__iexact="Bebidas calientes",
    ).select_related("account", "account__table")
    for item in table_items:
        finalized = item.account.status == TableAccount.Status.CLOSED
        rows.append(_row(item, "Mesa", f"{item.account.table.name} / cuenta {item.account_id}", finalized))

    grouped = defaultdict(lambda: {"quantity": 0, "total": Decimal("0.00")})
    product_totals = defaultdict(lambda: {"quantity": 0, "total": Decimal("0.00")})
    pending_total = Decimal("0.00")
    for row in rows:
        if not row["finalized"]:
            pending_total += row["total"]
            continue
        key = (row["product"], row["size"], row["milk"], row["unit_price"])
        grouped[key]["quantity"] += row["quantity"]
        grouped[key]["total"] += row["total"]
        product_totals[row["product"]]["quantity"] += row["quantity"]
        product_totals[row["product"]]["total"] += row["total"]
    summary = [
        {"product": key[0], "size": key[1], "milk": key[2], "unit_price": key[3], **values}
        for key, values in sorted(grouped.items())
    ]
    products = [{"name": name, **values} for name, values in sorted(product_totals.items())]
    return {
        "summary": summary, "products": products, "details": rows,
        "sales_total": sum((row["total"] for row in rows if row["finalized"]), Decimal("0.00")),
        "pending_total": pending_total,
    }
