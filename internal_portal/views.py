from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from django.urls import reverse
from django.shortcuts import render
from django.utils import timezone

from accounts.roles import OPERATIONAL_ROLES, SECTION_ROLE_MATRIX, role_required, user_has_any_role

from .navigation import SECTIONS

@role_required(*OPERATIONAL_ROLES)
def dashboard(request):
    role_names = list(request.user.groups.order_by("name").values_list("name", flat=True))
    allowed_sections = [
        {**section, "url": reverse(section["url_name"])}
        for section in SECTIONS
        if user_has_any_role(request.user, SECTION_ROLE_MATRIX[section["key"]])
    ]
    return render(
        request,
        "internal_portal/dashboard.html",
        {"role_names": role_names, "allowed_sections": allowed_sections},
    )


def _render_section(request, *, title, description):
    return render(
        request,
        "internal_portal/section_placeholder.html",
        {"title": title, "description": description},
    )


@role_required(*SECTION_ROLE_MATRIX["tables"])
def tables(request):
    return _render_section(request, title="Mesas", description="Aquí construiremos la operación de mesas.")


@role_required(*SECTION_ROLE_MATRIX["orders"])
def orders(request):
    return _render_section(request, title="Pedidos", description="Aquí construiremos la captura y seguimiento de pedidos.")


@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def deliveries(request):
    return _render_section(request, title="Repartos", description="Aquí construiremos la asignación y entrega de pedidos.")


@role_required(*SECTION_ROLE_MATRIX["reports"])
def reports(request):
    from menu.models import DailyProductStock, StockMovement
    from orders.models import Order, OrderItem
    from tables.models import TableAccount, TableAccountItem

    today = timezone.localdate()
    try:
        date_from = date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        date_from = today
    try:
        date_to = date.fromisoformat(request.GET.get("to", ""))
    except ValueError:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    channel = request.GET.get("channel", "all")
    if channel not in {"all", "tables", "orders", "pickup", "delivery"}:
        channel = "all"

    table_accounts = TableAccount.objects.filter(
        status=TableAccount.Status.CLOSED, closed_at__date__range=(date_from, date_to),
    ) if channel in {"all", "tables"} else TableAccount.objects.none()
    order_headers = Order.objects.filter(
        status__in=(Order.Status.PICKED_UP, Order.Status.DELIVERED),
        operating_date__range=(date_from, date_to),
    ) if channel in {"all", "orders", "pickup", "delivery"} else Order.objects.none()
    if channel in {"pickup", "delivery"}:
        order_headers = order_headers.filter(order_type=channel)

    table_count = table_accounts.count()
    order_count = order_headers.count()
    totals = {
        "tickets": table_count + order_count,
        "revenue": sum((value or Decimal("0") for value in table_accounts.values_list("subtotal_closed", flat=True)), Decimal("0"))
        + sum(order_headers.values_list("total", flat=True), Decimal("0")),
        "tables": table_count, "orders": order_count,
        "pickup": order_headers.filter(order_type=Order.OrderType.PICKUP).count(),
        "delivery": order_headers.filter(order_type=Order.OrderType.DELIVERY).count(),
    }
    package_counts = Counter({"running": 0, "executive": 0})
    course_counts = {position: defaultdict(Counter) for position in ("first", "second", "main")}
    individual_counts = Counter()
    all_product_counts = Counter()

    def package_type(item):
        if item.package_id and item.package:
            return item.package.package_type
        name = item.package_name_snapshot.lower()
        return "executive" if "ejecut" in name else "running" if "corrida" in name else "other"

    def collect(items, *, table=False):
        for item in items:
            quantity = item.quantity
            if item.item_type == "package":
                kind = package_type(item)
                package_counts[kind] += quantity
                names = (
                    item.first_course_snapshot if table else item.first_course_name_snapshot,
                    item.second_course_snapshot if table else item.second_course_name_snapshot,
                    item.main_course_snapshot if table else item.main_course_name_snapshot,
                )
                for position, name in zip(("first", "second", "main"), names):
                    if name:
                        course_counts[position][name][kind] += quantity
                        course_counts[position][name]["total"] += quantity
                        all_product_counts[name] += quantity
            elif not item.is_package_candidate and item.product_name_snapshot:
                individual_counts[item.product_name_snapshot] += quantity
                all_product_counts[item.product_name_snapshot] += quantity

    collect(TableAccountItem.objects.filter(account__in=table_accounts).select_related("package"), table=True)
    collect(OrderItem.objects.filter(order__in=order_headers).select_related("package"))

    def ranked(counter, limit=None):
        rows = [{"name": name, "quantity": quantity} for name, quantity in counter.most_common(limit)]
        maximum = rows[0]["quantity"] if rows else 0
        for row in rows:
            row["percentage"] = round(row["quantity"] * 100 / maximum) if maximum else 0
        return rows

    def course_rows(position):
        return [
            {"name": name, "running": values["running"], "executive": values["executive"], "total": values["total"]}
            for name, values in sorted(course_counts[position].items(), key=lambda pair: (-pair[1]["total"], pair[0]))
        ]

    daily_stocks = DailyProductStock.objects.filter(
        stock_type=DailyProductStock.StockType.DAILY,
        date__range=(date_from, date_to), is_tracked=True,
    ).select_related("product").prefetch_related("movements")
    if channel == "tables":
        daily_stocks = daily_stocks.filter(channel=DailyProductStock.Channel.TABLE)
    elif channel in {"orders", "pickup", "delivery"}:
        daily_stocks = daily_stocks.filter(channel=DailyProductStock.Channel.ORDERS)

    inventory_order_headers = Order.objects.filter(
        status__in=(Order.Status.PICKED_UP, Order.Status.DELIVERED),
        operating_date__range=(date_from, date_to),
    )
    finalized_order_item_ids = set(OrderItem.objects.filter(
        order__in=inventory_order_headers,
    ).values_list("pk", flat=True))
    finalized_table_item_ids = set(TableAccountItem.objects.filter(
        account__in=table_accounts,
    ).values_list("pk", flat=True))
    inventory_rows = []
    inventory_totals = Counter()
    for stock in daily_stocks:
        additions = losses = sold_signed = active_signed = 0
        for movement in stock.movements.all():
            if movement.reason == StockMovement.Reason.ADJUSTMENT:
                if movement.quantity > 0:
                    additions += movement.quantity
                else:
                    losses += abs(movement.quantity)
            if movement.reason not in (StockMovement.Reason.RESERVATION, StockMovement.Reason.RELEASE):
                continue
            is_final = (
                movement.reference_type == "order_item" and movement.reference_id in finalized_order_item_ids
            ) or (
                movement.reference_type == "table_item" and movement.reference_id in finalized_table_item_ids
            )
            if is_final:
                sold_signed += movement.quantity
            else:
                active_signed += movement.quantity
        prepared = stock.initial_quantity + additions
        row = {
            "date": stock.date, "name": stock.item_name,
            "channel": stock.get_channel_display(), "initial": stock.initial_quantity,
            "additions": additions, "prepared": prepared,
            "sold": max(0, -sold_signed), "committed": max(0, -active_signed),
            "losses": losses, "remaining": stock.available_quantity,
        }
        inventory_rows.append(row)
        for key in ("initial", "additions", "prepared", "sold", "committed", "losses", "remaining"):
            inventory_totals[key] += row[key]
    inventory_rows.sort(key=lambda row: (row["date"], row["name"], row["channel"]), reverse=True)

    return render(request, "internal_portal/sales_report.html", {
        "date_from": date_from, "date_to": date_to, "channel": channel,
        "totals": totals, "running_count": package_counts["running"],
        "executive_count": package_counts["executive"],
        "individual_total": sum(individual_counts.values()),
        "first_courses": course_rows("first"), "second_courses": course_rows("second"),
        "main_courses": course_rows("main"), "individual_products": ranked(individual_counts),
        "top_products": ranked(all_product_counts, 10),
        "inventory_rows": inventory_rows, "inventory_totals": inventory_totals,
        "inventory_combines_orders": channel in {"pickup", "delivery"},
    })
