from decimal import Decimal

from django.utils import timezone

from orders.models import CustomerDebt


def _person_name(person):
    if not person:
        return "Sin asignar"
    return person.get_full_name() or person.username


def _configuration_details(item):
    snapshot = item.configuration_snapshot or {}
    if isinstance(snapshot, dict):
        return [str(value) for value in snapshot.get("differences", []) if value]
    return []


def printable_item(item, quantity=None):
    """Convierte partidas de Mesa y Pedido a una forma común para los tickets."""
    is_package = item.item_type == item.ItemType.PACKAGE
    name = item.package_name_snapshot if is_package else item.product_name_snapshot
    details = []
    if is_package:
        details.extend(filter(None, (
            getattr(item, "first_course_snapshot", "") or getattr(item, "first_course_name_snapshot", ""),
            getattr(item, "second_course_snapshot", "") or getattr(item, "second_course_name_snapshot", ""),
            getattr(item, "main_course_snapshot", "") or getattr(item, "main_course_name_snapshot", ""),
        )))
        if item.with_water:
            details.append(f"Con agua: {item.water_name_snapshot}" if item.water_name_snapshot else "Con agua del día")
        details.append("Con tortillas" if item.tortillas else "Sin tortillas")
        details.append("Con frijoles" if item.beans else "Sin frijoles")
        if getattr(item, "egg_name_snapshot", ""):
            details.append(f"Agregar: {item.egg_name_snapshot}")
    else:
        details.extend(_configuration_details(item))
    chicken_piece = getattr(item, "chicken_piece", "")
    if chicken_piece:
        details.append({"leg": "Pieza: pierna", "thigh": "Pieza: muslo"}.get(chicken_piece, chicken_piece))
    comment = getattr(item, "customization_comment", "").strip()
    selected_quantity = quantity if quantity is not None else item.quantity
    unit_price = item.unit_price
    return {
        "id": item.pk,
        "name": name,
        "quantity": selected_quantity,
        "available_quantity": item.quantity,
        "unit_price": unit_price,
        "subtotal": unit_price * selected_quantity,
        "details": details,
        "comment": comment,
        "is_customized": getattr(item, "is_customized", False),
    }


def selected_printable_items(request, queryset):
    """Lee casillas y cantidades del selector sin aceptar partidas ajenas al ticket."""
    items = list(queryset)
    if request.method != "POST":
        return None, items
    selected = []
    errors = []
    for item in items:
        if request.POST.get(f"item_{item.pk}") != "on":
            continue
        try:
            quantity = int(request.POST.get(f"quantity_{item.pk}", "1"))
        except (TypeError, ValueError):
            quantity = 0
        if quantity < 1 or quantity > item.quantity:
            errors.append(f"La cantidad de {printable_item(item)['name']} debe estar entre 1 y {item.quantity}.")
            continue
        selected.append(printable_item(item, quantity))
    if not selected and not errors:
        errors.append("Selecciona al menos una partida para la comanda de cocina.")
    return selected, errors


def table_print_context(account):
    subtotal = account.subtotal_closed
    if subtotal is None:
        subtotal = sum((item.subtotal for item in account.items.all()), Decimal("0"))
    tip = account.tip_amount or Decimal("0")
    return {
        "source_kind": "table",
        "reference": account.table.name,
        "folio": "",
        "print_mode_label": "MESAS",
        "table_name": account.table.name,
        "split_label": account.split_label,
        "customer_name": account.customer_name or "Cliente de mesa",
        "responsible": _person_name(account.assigned_waiter),
        "opened_at": account.opened_at,
        "requested_for": None,
        "order_type": "Servicio en mesa",
        "address": "",
        "references": "",
        "phone": "",
        "general_note": "",
        "payment_method": account.get_payment_method_display() if account.payment_method else "Pendiente",
        "cash_tendered": account.cash_tendered,
        "change": account.change_given,
        "subtotal": subtotal,
        "tip": tip,
        "total": account.total_paid if account.total_paid is not None else subtotal + tip,
        "printed_at": timezone.now(),
    }


def order_print_context(order):
    address = ""
    if order.order_type == order.OrderType.DELIVERY:
        address = f"{order.street} {order.exterior_number}".strip()
        if order.interior_number:
            address += f", int. {order.interior_number}"
        if order.neighborhood:
            address += f" · {order.neighborhood}"
    return {
        "source_kind": "order",
        "reference": f"Pedido {order.formatted_number}",
        "folio": order.formatted_number,
        "print_mode_label": "A DOMICILIO" if order.order_type == order.OrderType.DELIVERY else "RECOGER",
        "table_name": "",
        "customer_name": order.customer_name or "Sin nombre",
        "responsible": _person_name(order.created_by),
        "opened_at": order.created_at,
        "requested_for": order.requested_for,
        "order_type": order.get_order_type_display(),
        "address": address,
        "references": order.references,
        "phone": order.phone,
        "general_note": order.notes,
        "payment_method": order.get_payment_method_display() if order.payment_method else "Pendiente",
        "cash_tendered": order.cash_tendered,
        "change": order.change_required,
        "subtotal": order.total,
        "tip": order.delivery_tip_amount,
        "total": order.total_with_delivery_tip,
        "printed_at": timezone.now(),
        "take_terminal": order.payment_method == order.PaymentMethod.CARD and order.order_type == order.OrderType.DELIVERY,
        # NOTA TEMPORAL PARA APRENDIZAJE: el desarrollador pidió que, cuando el
        # saldo a favor cubrió parte o todo el pedido, el ticket de cobro aclare
        # cuánto se descontó y cuánto le queda al cliente — no sólo el método de
        # pago ("Saldo a favor" ya sale solo ahí cuando cubrió todo). amount_due es
        # lo que realmente falta cobrar (0 si el saldo cubrió todo). Borra esta
        # nota después de leerla.
        "credit_applied": order.credit_applied if order.credit_applied else None,
        "credit_balance_remaining": order.agenda_customer.credit_balance if order.credit_applied and order.agenda_customer_id else None,
        "amount_due": order.amount_due if order.credit_applied else None,
        # NOTA TEMPORAL PARA APRENDIZAJE: espejo de las líneas de saldo a favor de
        # arriba, pero para adeudo — el desarrollador pidió que el ticket de cobro
        # siempre avise si el cliente ya debe de pedidos anteriores, sin importar
        # cómo se esté cobrando este pedido en particular (es sólo informativo,
        # igual que el aviso que ya se ve durante la captura y en los tableros).
        # Borra esta nota después de leerla.
        **_pending_debt_print_fields(order),
    }


def _pending_debt_print_fields(order):
    if not order.agenda_customer_id:
        return {"debt_pending_balance": None, "debt_pending_count": None}
    open_debts = list(order.agenda_customer.debts.filter(
        status__in=(CustomerDebt.Status.PENDING, CustomerDebt.Status.PARTIAL),
    ))
    balance = sum((debt.balance for debt in open_debts), Decimal("0"))
    if balance <= 0:
        return {"debt_pending_balance": None, "debt_pending_count": None}
    return {"debt_pending_balance": balance, "debt_pending_count": len(open_debts)}
