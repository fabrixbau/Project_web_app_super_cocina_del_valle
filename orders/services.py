# NOTA TEMPORAL PARA APRENDIZAJE:
# La asignación de reparto usa bloqueo y valida quién puede cerrar una entrega.
# Centralizamos la máquina de estados y su historial. El backend decide qué acción sigue;
# la plantilla solo muestra esas opciones. Borra esta nota después de leerla.
# El checkout nuevo recorre todas las partidas resueltas y calcula otra vez sus precios.
# También crea o atiende la notificación dentro de la misma transacción del pedido.
# Este servicio guarda encabezado y partida dentro de una sola transacción. Si algo falla,
# no queda medio pedido guardado. También vuelve a leer el precio y genera el folio diario
# con bloqueo para evitar números repetidos. Borra esta nota después de leerla.

from datetime import datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER, user_has_any_role
from menu.inventory import release_stock, reserve_stock
from menu.models import DailyMenu, DailyProductStock, MealPackage, Product, StockMovement
from menu.packaging import selected_packaging_products
from menu.selection import resolve_product_selection
from notifications.models import InternalNotification

from .models import Customer, CustomerAddress, CustomerDebt, CustomerDebtMovement, DailyOrderCounter, Order, OrderItem, OrderStatusHistory
from .phones import phone_key


ACTION_LABELS = {
    "confirm": "Confirmar pedido",
    "cancel": "Cancelar pedido",
    "start_preparing": "Iniciar preparación",
    "mark_ready": "Marcar como listo",
    "dispatch_delivery": "Marcar como en reparto",
    "complete_pickup": "Marcar como recogido",
    "complete_delivery": "Marcar como entregado",
    "restart_cycle": "Iniciar nuevo ciclo",
}


def can_update_order_payment(*, order, actor):
    """Return whether this operator may change the order payment instruction."""
    if user_has_any_role(actor, (ADMIN,)):
        return True
    if not user_has_any_role(actor, (ORDER_TAKER, WAITER)):
        return False
    if order.order_type == Order.OrderType.DELIVERY:
        return order.status not in {Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED}
    if order.order_type == Order.OrderType.PICKUP:
        return order.status != Order.Status.PICKED_UP
    return True


def _inventory_channel(order_type):
    return DailyProductStock.Channel.ORDERS


def _daily_product_ids(daily_menu):
    return {product_id for product_id in (
        daily_menu.water_product_id, daily_menu.chicken_consomme_id,
        daily_menu.variable_first_course_id, daily_menu.second_course_one_id,
        daily_menu.second_course_two_id, daily_menu.chicken_stew_id,
        daily_menu.beef_stew_id, daily_menu.varied_stew_id, daily_menu.beans_order_id,
    ) if product_id}


def _order_item_requirements(item, daily_menu):
    if item.item_type == OrderItem.ItemType.PRODUCT:
        if not item.product_id:
            return []
        return [DailyProductStock.ItemKind.BREAD] if item.product.uses_bread_stock else [item.product]
    requirements = [product for product in (
        item.first_course, item.second_course, item.main_course,
        (item.water_product or (daily_menu.water_product if daily_menu else None)) if item.with_water else None,
        (item.beans_product or (daily_menu.beans_order if daily_menu else None)) if item.beans else None,
        item.egg_product,
    ) if product]
    if item.tortillas:
        requirements.append(DailyProductStock.ItemKind.TORTILLAS)
    if item.bread:
        requirements.append(DailyProductStock.ItemKind.BREAD)
    return requirements


def _change_order_item_stock(*, item, quantity, actor, reserve, channel=None):
    if not quantity:
        return
    order = item.order
    daily_menu = item.daily_menu or DailyMenu.objects.filter(date=order.operating_date).first()
    daily_ids = _daily_product_ids(daily_menu) if daily_menu else set()
    selected_channel = channel or _inventory_channel(order.order_type)
    for requirement in _order_item_requirements(item, daily_menu):
        is_product = isinstance(requirement, Product)
        required = bool((not is_product and requirement == DailyProductStock.ItemKind.BREAD) or (daily_menu and ((is_product and requirement.pk in daily_ids) or not is_product)))
        filters = {
            "date": order.operating_date, "channel": selected_channel,
            "stock_type": DailyProductStock.StockType.DAILY,
            "item_kind": DailyProductStock.ItemKind.PRODUCT if is_product else requirement,
            "product": requirement if is_product else None,
        }
        if is_product and daily_menu and requirement.pk == daily_menu.chicken_stew_id:
            filters["chicken_piece"] = item.chicken_piece
        else:
            filters["chicken_piece"] = ""
        stock = (
            DailyProductStock.objects.select_for_update()
            .filter(**filters)
            .order_by("pk")
            .first()
        )
        if not stock and filters["chicken_piece"]:
            # Menús publicados antes del conteo por pieza conservan temporalmente
            # una bolsa general hasta que se capture su reparto entre pierna y muslo.
            legacy_filters = {**filters, "chicken_piece": ""}
            stock = (
                DailyProductStock.objects.select_for_update()
                .filter(**legacy_filters)
                .order_by("pk")
                .first()
            )
        if not stock and is_product and not required:
            stock = (
                DailyProductStock.objects.select_for_update()
                .filter(
                    stock_type=DailyProductStock.StockType.FIXED,
                    product=requirement,
                    channel=DailyProductStock.Channel.SHARED,
                    is_tracked=True,
                )
                .order_by("pk")
                .first()
            )
        if required and not stock:
            name = requirement.name if is_product else dict(DailyProductStock.ItemKind.choices)[requirement]
            raise ValidationError(
                f"{name} no tiene raciones configuradas para {dict(DailyProductStock.Channel.choices)[selected_channel].lower()}."
            )
        if not stock:
            continue
        operation = reserve_stock if reserve else release_stock
        operation(
            stock=stock, quantity=quantity, actor=actor,
            reference_type="order_item", reference_id=item.pk,
            note=f"Pedido {order.formatted_number}: {item.product_name_snapshot or item.package_name_snapshot}",
        )


def _move_order_stock_channel(*, order, old_type, actor):
    old_channel = _inventory_channel(old_type)
    new_channel = _inventory_channel(order.order_type)
    if old_channel == new_channel:
        return
    for item in order.items.select_for_update().all():
        _change_order_item_stock(
            item=item, quantity=item.quantity, actor=actor, reserve=False, channel=old_channel,
        )
        _change_order_item_stock(
            item=item, quantity=item.quantity, actor=actor, reserve=True, channel=new_channel,
        )


@transaction.atomic
def create_customer_debt(*, order, actor, note=""):
    """Move a delivered order into the ledger, completing an active delivery first."""
    # NOTA TEMPORAL PARA APRENDIZAJE: PostgreSQL no permite FOR UPDATE sobre el lado
    # nullable de un LEFT JOIN. Bloqueamos solamente Order y leemos agenda_customer
    # después mediante una consulta normal. Borra esta nota después de leerla.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.OUT_FOR_DELIVERY:
        order = transition_order(order=order, action="complete_delivery", actor=actor)
    if order.status not in {Order.Status.DELIVERED, Order.Status.PICKED_UP}:
        raise ValidationError("El pedido debe estar entregado o recogido antes de dejarlo a cuenta.")
    if not order.agenda_customer_id:
        raise ValidationError("Vincula un cliente de la agenda antes de dejar este pedido a cuenta.")
    if hasattr(order, "customer_debt"):
        raise ValidationError("Este pedido ya está registrado en cuentas por cobrar.")
    return CustomerDebt.objects.create(
        customer=order.agenda_customer, order=order, original_amount=order.total,
        created_by=actor, note=" ".join(note.split()),
    )


@transaction.atomic
def register_customer_debt_payment(*, debt, amount, payment_method, actor, note=""):
    debt = CustomerDebt.objects.select_for_update().get(pk=debt.pk)
    if debt.status == CustomerDebt.Status.FORGIVEN:
        raise ValidationError("Reabre el adeudo antes de registrar un abono.")
    try:
        amount = Decimal(amount)
    except Exception as error:
        raise ValidationError("Escribe un importe válido.") from error
    if amount <= 0 or amount > debt.balance:
        raise ValidationError(f"El abono debe ser mayor a cero y no superar el saldo de ${debt.balance:.2f}.")
    if payment_method not in Order.PaymentMethod.values:
        raise ValidationError("Selecciona cómo se recibió el abono.")
    debt.paid_amount += amount
    debt.status = CustomerDebt.Status.PAID if debt.paid_amount >= debt.original_amount else CustomerDebt.Status.PARTIAL
    debt.save(update_fields=("paid_amount", "status", "updated_at"))
    CustomerDebtMovement.objects.create(
        debt=debt, action=CustomerDebtMovement.Action.PAYMENT, amount=amount,
        payment_method=payment_method, note=" ".join(note.split()), registered_by=actor,
    )
    return debt


@transaction.atomic
def set_customer_debt_forgiven(*, debt, forgiven, actor, note=""):
    debt = CustomerDebt.objects.select_for_update().get(pk=debt.pk)
    if forgiven:
        if debt.status in {CustomerDebt.Status.PAID, CustomerDebt.Status.FORGIVEN}:
            raise ValidationError("Este adeudo ya está cerrado.")
        action = CustomerDebtMovement.Action.FORGIVE
        amount = debt.balance
        debt.status = CustomerDebt.Status.FORGIVEN
    else:
        if debt.status != CustomerDebt.Status.FORGIVEN:
            raise ValidationError("Sólo un adeudo condonado puede reabrirse.")
        action = CustomerDebtMovement.Action.REOPEN
        amount = Decimal("0")
        debt.status = CustomerDebt.Status.PARTIAL if debt.paid_amount else CustomerDebt.Status.PENDING
    debt.save(update_fields=("status", "updated_at"))
    CustomerDebtMovement.objects.create(
        debt=debt, action=action, amount=amount,
        note=" ".join(note.split()), registered_by=actor,
    )
    return debt


@transaction.atomic
def update_cashier_payment(*, order, payment_method, cash_amount, actor):
    """Persist the payment instruction selected at the cash desk."""
    # NOTA TEMPORAL PARA APRENDIZAJE: al cambiar cómo pagará el cliente anulamos una
    # confirmación anterior de cambio. Caja deberá confirmar otra vez el dinero físico
    # porque el importe pudo cambiar. Borra esta nota después de leerla.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not can_update_order_payment(order=order, actor=actor):
        raise ValidationError(
            "La forma de pago ya no puede modificarse en el estado actual del pedido."
        )
    if payment_method not in {"", *Order.PaymentMethod.values}:
        raise ValidationError("Selecciona efectivo, terminal o transferencia.")
    order.payment_method = payment_method
    order.cash_settlement_confirmed = False
    order.cash_settlement_by = None
    order.cash_settlement_at = None
    if payment_method == Order.PaymentMethod.CASH:
        if cash_amount == "":
            order.needs_change = False
            order.cash_tendered = None
        elif cash_amount == "exact":
            order.needs_change = False
            order.cash_tendered = order.total
        else:
            try:
                tendered = Decimal(cash_amount)
            except Exception as error:
                raise ValidationError("Selecciona el billete o indica pago exacto.") from error
            if tendered < order.total:
                raise ValidationError("El efectivo indicado no cubre el total del pedido.")
            order.cash_tendered = tendered
            order.needs_change = tendered > order.total
    else:
        order.needs_change = False
        order.cash_tendered = None
    if payment_method != Order.PaymentMethod.TRANSFER:
        order.delivery_tip_amount = 0
        order.delivery_tip_recipient = None
        order.delivery_tip_updated_by = None
        order.delivery_tip_updated_at = None
    order.save(update_fields=(
        "payment_method", "needs_change", "cash_tendered", "cash_settlement_confirmed",
        "cash_settlement_by", "cash_settlement_at", "delivery_tip_amount",
        "delivery_tip_recipient", "delivery_tip_updated_by", "delivery_tip_updated_at",
        "updated_at",
    ))
    return order


@transaction.atomic
def confirm_cash_settlement(*, order, actor, confirmed=True):
    """Record that the courier returned/settled the change with Cashier."""
    # Bloqueamos sólo Order: delivery_person es nullable y PostgreSQL no permite
    # FOR UPDATE sobre ese lado de un OUTER JOIN.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("La entrega de cambio sólo aplica a pedidos a domicilio.")
    if not order.delivery_person:
        raise ValidationError("Asigna un repartidor antes de entregar el cambio.")
    if order.payment_method != Order.PaymentMethod.CASH:
        raise ValidationError("Este pedido no está marcado para pago en efectivo.")
    # NOTA TEMPORAL PARA APRENDIZAJE: confirmar la devolución también culmina la
    # entrega, pero recorremos la máquina de estados para conservar toda la bitácora.
    # Si cualquier transición falla, la transacción revierte también la conciliación.
    # Borra esta nota después de leerla.
    if confirmed:
        safety_counter = 0
        while order.status != Order.Status.DELIVERED and safety_counter < 7:
            actions = [action for action in available_order_actions(order) if action != "cancel"]
            if not actions or actions[0] == "restart_cycle":
                raise ValidationError("El estado actual no permite completar la entrega.")
            order = transition_order(order=order, action=actions[0], actor=actor)
            safety_counter += 1
        if order.status != Order.Status.DELIVERED:
            raise ValidationError("No fue posible completar el estado de la entrega.")
    order.cash_settlement_confirmed = confirmed
    order.cash_settlement_by = actor if confirmed else None
    order.cash_settlement_at = timezone.now() if confirmed else None
    order.save(update_fields=("cash_settlement_confirmed", "cash_settlement_by", "cash_settlement_at", "updated_at"))
    return order


@transaction.atomic
def set_cashier_release(*, order, actor, released=True):
    """Finish or restore the order's independent cash-desk review."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if released:
        if not order.payment_method:
            raise ValidationError("Selecciona la forma de pago antes de liberar el pedido.")
        if order.order_type == Order.OrderType.DELIVERY and not order.delivery_person_id:
            raise ValidationError("Asigna un repartidor antes de liberar la entrega.")
        # NOTA TEMPORAL PARA APRENDIZAJE: liberar en Caja completa de una vez las
        # transiciones operativas previas, pero usa transition_order para conservar
        # todas en el historial y sus validaciones. Borra esta nota después de leerla.
        target_status = (
            Order.Status.OUT_FOR_DELIVERY
            if order.order_type == Order.OrderType.DELIVERY
            else Order.Status.PICKED_UP
        )
        safety_counter = 0
        while order.status != target_status and safety_counter < 7:
            actions = [action for action in available_order_actions(order) if action != "cancel"]
            if not actions:
                raise ValidationError("El estado actual no permite completar el flujo de Caja.")
            order = transition_order(order=order, action=actions[0], actor=actor)
            safety_counter += 1
        if order.status != target_status:
            raise ValidationError("No fue posible completar el flujo operativo de Caja.")
        order.cashier_released_at = timezone.now()
        order.cashier_released_by = actor
    else:
        order.cashier_released_at = None
        order.cashier_released_by = None
    order.save(update_fields=("cashier_released_at", "cashier_released_by", "updated_at"))
    return order


def scheduled_initial_status(order):
    # NOTA TEMPORAL PARA APRENDIZAJE: una hora o más convierte la captura en
    # Programado. Un pedido más cercano entra directamente a preparación.
    # El backend decide para no depender del reloj del navegador. Borra esta nota.
    if order.requested_for and order.created_at:
        if order.requested_for >= order.created_at + timedelta(hours=1):
            return Order.Status.SCHEDULED
    return Order.Status.PREPARING


def _normalize_phone(value):
    return phone_key(value)


def sync_order_customer_agenda(order, form_data):
    """Link a pickup contact or create/update the contact and address for delivery."""
    # NOTA TEMPORAL PARA APRENDIZAJE: enlazamos el pedido con la ficha creada. En
    # autoguardados posteriores actualizamos esa misma dirección y evitamos duplicarla
    # mientras el telefonista continúa escribiendo. Borra esta nota después de leerla.
    if order.order_type != Order.OrderType.DELIVERY:
        # NOTA TEMPORAL PARA APRENDIZAJE: Recoger no crea contactos implícitamente,
        # pero sí conserva la ficha que el operador eligió. No asociamos domicilio
        # porque la entrega sucede en mostrador. Borra esta nota después de leerla.
        customer_id = form_data.get("agenda_customer_id")
        customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
        order.agenda_customer = customer
        order.agenda_address = None
        order.save(update_fields=("agenda_customer", "agenda_address", "updated_at"))
        return order
    name = " ".join(form_data.get("customer_name", "").split())
    street = form_data.get("street", "").strip()
    exterior = form_data.get("exterior_number", "").strip()
    if not name or not street or not exterior:
        return order
    phone = form_data.get("phone", "").strip()
    normalized_phone = _normalize_phone(phone)
    customer_id = form_data.get("agenda_customer_id")
    customer = Customer.objects.filter(pk=customer_id).first() if customer_id else None
    phone_match = Customer.objects.filter(phone_key=normalized_phone).first() if normalized_phone else None
    # Si el teléfono pertenece a otra ficha, conservamos el pedido pero no tocamos
    # la agenda hasta que el operador elija expresamente ese contacto.
    if phone_match and (customer is None or phone_match.pk != customer.pk):
        return order
    if customer is None and phone_match:
        customer = phone_match
    if customer is None and not normalized_phone:
        customer = Customer.objects.filter(name__iexact=name).first()
    if customer is None:
        customer = Customer.objects.create(name=name, phone=phone)
    else:
        customer.name = name
        if phone:
            customer.phone = phone
        customer.save(update_fields=("name", "phone", "updated_at"))

    address_id = form_data.get("agenda_address_id")
    address = CustomerAddress.objects.filter(pk=address_id, customer=customer).first() if address_id else None
    if address is None:
        address = CustomerAddress.objects.filter(
            customer=customer, street__iexact=street, exterior_number__iexact=exterior,
            interior_number__iexact=form_data.get("interior_number", "").strip(),
        ).first()
    values = {
        "street": street, "exterior_number": exterior,
        "interior_number": form_data.get("interior_number", "").strip(),
        "neighborhood": form_data.get("neighborhood", "").strip(),
        "references": form_data.get("references", "").strip(),
    }
    if address is None:
        address = CustomerAddress.objects.create(customer=customer, **values)
    else:
        for field, value in values.items():
            setattr(address, field, value)
        address.save(update_fields=(*values.keys(), "updated_at"))
    order.agenda_customer = customer
    order.agenda_address = address
    order.save(update_fields=("agenda_customer", "agenda_address", "updated_at"))
    return order


@transaction.atomic
def save_internal_order(*, form_data, actor, order=None):
    """Crea el folio una sola vez o actualiza sus datos sin borrar el ticket."""
    today = timezone.localdate()
    if order is None:
        counter, _ = DailyOrderCounter.objects.select_for_update().get_or_create(operating_date=today)
        counter.last_number += 1
        counter.save(update_fields=("last_number",))
        order = Order(
            daily_number=counter.last_number, operating_date=today,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            created_by=actor, total=0,
        )
    else:
        order = Order.objects.select_for_update().get(pk=order.pk)
    old_type = order.order_type
    order.order_type = form_data["order_type"]
    if order.pk and old_type != order.order_type:
        _move_order_stock_channel(order=order, old_type=old_type, actor=actor)
    order.customer_name = " ".join(form_data["customer_name"].split())
    order.phone = form_data.get("phone", "").strip()
    order.requested_for = form_data.get("requested_for")
    order.requested_date = form_data.get("requested_date")
    order.requested_time = form_data.get("requested_time")
    is_delivery = order.order_type == Order.OrderType.DELIVERY
    for field in ("street", "exterior_number", "interior_number", "neighborhood", "references"):
        setattr(order, field, form_data.get(field, "").strip() if is_delivery else "")
    order.notes = form_data.get("notes", "").strip()
    order.payment_method = form_data["payment_method"]
    order.needs_change = form_data["needs_change"]
    order.cash_tendered = form_data["cash_tendered"]
    order.save()
    sync_order_customer_agenda(order, form_data)
    if not order.status_history.exists():
        OrderStatusHistory.objects.create(order=order, from_status="", to_status=order.status, changed_by=actor)
    return order


@transaction.atomic
def autosave_internal_order_customer(*, order, form_data, actor=None):
    """Persiste el panel del cliente sin exigir que el pedido ya esté completo."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    old_type = order.order_type
    order.order_type = form_data["order_type"]
    if old_type != order.order_type:
        _move_order_stock_channel(order=order, old_type=old_type, actor=actor)
    order.customer_name = " ".join(form_data.get("customer_name", "").split())
    order.phone = form_data.get("phone", "").strip()
    order.requested_date = form_data.get("requested_date")
    order.requested_time = form_data.get("requested_time")
    order.requested_for = (
        timezone.make_aware(datetime.combine(order.requested_date, order.requested_time))
        if order.requested_date and order.requested_time else None
    )
    for field in ("street", "exterior_number", "interior_number", "neighborhood", "references"):
        setattr(order, field, form_data.get(field, "").strip())
    order.notes = form_data.get("notes", "").strip()
    order.payment_method = form_data.get("payment_method", "")
    order.needs_change = form_data.get("needs_change", False)
    order.cash_tendered = form_data.get("cash_tendered")
    if order.order_type != Order.OrderType.DELIVERY or order.payment_method not in {
        Order.PaymentMethod.CARD, Order.PaymentMethod.TRANSFER,
    }:
        order.delivery_tip_amount = 0
        order.delivery_tip_recipient = None
        order.delivery_tip_updated_by = None
        order.delivery_tip_updated_at = None
    order.save(update_fields=(
        "order_type", "customer_name", "phone", "requested_date", "requested_time",
        "requested_for", "street", "exterior_number", "interior_number",
        "neighborhood", "references", "notes", "payment_method", "needs_change", "cash_tendered",
        "delivery_tip_amount", "delivery_tip_recipient", "delivery_tip_updated_by",
        "delivery_tip_updated_at", "updated_at",
    ))
    sync_order_customer_agenda(order, form_data)
    return order


@transaction.atomic
def start_internal_order(*, order_type, actor):
    if order_type not in Order.OrderType.values:
        raise ValidationError("Selecciona una modalidad válida.")
    now = timezone.localtime()
    today = now.date()
    counter, _ = DailyOrderCounter.objects.select_for_update().get_or_create(operating_date=today)
    counter.last_number += 1
    counter.save(update_fields=("last_number",))
    order = Order.objects.create(
        daily_number=counter.last_number, operating_date=today, order_type=order_type,
        source=Order.Source.INTERNAL, status=Order.Status.DRAFT, created_by=actor,
        # NOTA TEMPORAL PARA APRENDIZAJE: Recoger representa normalmente una venta
        # inmediata de mostrador. Guardamos ese nombre desde el inicio, pero la interfaz
        # permite reemplazarlo rápidamente si el cliente sí proporciona uno. Borra esta nota.
        customer_name="Mostrador" if order_type == Order.OrderType.PICKUP else "",
        phone="", total=0, requested_date=today,
        requested_time=now.time().replace(second=0, microsecond=0),
        neighborhood="del valle centro" if order_type == Order.OrderType.DELIVERY else "",
    )
    OrderStatusHistory.objects.create(order=order, from_status="", to_status=Order.Status.DRAFT, changed_by=actor)
    return order


@transaction.atomic
def close_internal_order_capture(*, order, actor):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.DRAFT:
        return order
    if not order.items.exists():
        raise ValidationError("Agrega al menos un producto antes de cerrar el ticket.")
    if order.items.filter(is_package_candidate=True).exists():
        raise ValidationError("Hay una comida incompleta. Agrega los tiempos faltantes o elimina sus componentes.")
    if not order.customer_name.strip():
        raise ValidationError("Escribe el nombre del cliente.")
    if not order.requested_date or not order.requested_time:
        raise ValidationError("Completa la fecha y hora de entrega.")
    if order.order_type == Order.OrderType.DELIVERY:
        if not order.payment_method:
            raise ValidationError("Selecciona la forma de pago de la entrega antes de cerrar.")
        required = (order.street, order.exterior_number)
        if not all(value.strip() for value in required):
            raise ValidationError("Completa la calle y el número exterior de la entrega.")
    if order.payment_method == Order.PaymentMethod.CASH and order.needs_change:
        if order.cash_tendered is None or order.cash_tendered < order.total:
            raise ValidationError("Actualiza el efectivo: la cantidad no cubre el total.")
    previous = order.status
    order.status = scheduled_initial_status(order)
    order.save(update_fields=("status", "updated_at"))
    OrderStatusHistory.objects.create(order=order, from_status=previous, to_status=order.status, changed_by=actor)
    return order


def recalculate_order_total(order):
    order.total = sum((item.subtotal for item in order.items.all()), start=0)
    update_fields = ["total", "updated_at"]
    if order.payment_method == Order.PaymentMethod.CASH and not order.needs_change:
        order.cash_tendered = order.total
        update_fields.append("cash_tendered")
    order.save(update_fields=update_fields)


@transaction.atomic
def add_internal_order_product(
    *, order, product, actor, raw_option_ids=None, comment="", require_individual=True,
    is_package_candidate=False, chicken_piece="", daily_menu=None,
):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in {Order.Status.PICKED_UP, Order.Status.DELIVERED, Order.Status.CANCELED}:
        raise ValidationError("Este pedido ya no admite productos.")
    product = Product.objects.select_for_update().prefetch_related("option_groups__options").get(pk=product.pk)
    if not product.is_available or (require_individual and not product.is_sold_individually):
        raise ValidationError("El producto ya no está disponible por orden.")
    if daily_menu is None and not require_individual:
        candidate_menu = DailyMenu.objects.filter(
            date=order.operating_date, status=DailyMenu.Status.PUBLISHED,
        ).first()
        if candidate_menu and product.pk in _daily_product_ids(candidate_menu):
            daily_menu = candidate_menu
    selection = resolve_product_selection(product, raw_option_ids, comment)
    item = OrderItem.objects.select_for_update().filter(
        order=order, item_type=OrderItem.ItemType.PRODUCT, product=product,
        configuration_signature=selection["signature"], is_package_candidate=is_package_candidate,
        chicken_piece=chicken_piece, daily_menu=daily_menu,
    ).first()
    if item:
        item.quantity += 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    else:
        item = OrderItem.objects.create(
            order=order, item_type=OrderItem.ItemType.PRODUCT, product=product,
            product_name_snapshot=product.name, unit_price=selection["unit_price"],
            quantity=1, subtotal=selection["unit_price"], tortillas=False, beans=False,
            configuration_snapshot=selection["snapshot"],
            configuration_signature=selection["signature"],
            customization_comment=selection["comment"], is_customized=selection["is_customized"],
            is_package_candidate=is_package_candidate, chicken_piece=chicken_piece,
            daily_menu=daily_menu,
        )
    _change_order_item_stock(item=item, quantity=1, actor=actor, reserve=True)
    recalculate_order_total(order)
    return item


def _consume_internal_candidate(*, order, product_id, actor, chicken_product_id=None, chicken_piece=""):
    queryset = OrderItem.objects.select_for_update().filter(
        order=order, product_id=product_id, item_type=OrderItem.ItemType.PRODUCT,
        is_package_candidate=True,
    )
    if product_id == chicken_product_id:
        queryset = queryset.filter(chicken_piece=chicken_piece)
    item = queryset.order_by("-id").first()
    if not item:
        raise ValidationError("Cambió el ticket y no encontramos todos los tiempos seleccionados.")
    _change_order_item_stock(item=item, quantity=1, actor=actor, reserve=False)
    if item.quantity == 1:
        item.delete()
    else:
        item.quantity -= 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))


@transaction.atomic
def add_internal_auto_meal_component(
    *, order, product, daily_menu, completed_selection, actor, chicken_piece="",
    raw_option_ids=None, comment="", with_water=False, tortillas=False, bread=False, beans=False,
    package_comment="", egg_product=None,
):
    """Guarda un tiempo pendiente y lo convierte en paquete al completar los tres espacios."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    daily_menu = DailyMenu.objects.select_for_update().get(
        pk=daily_menu.pk, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    daily_ids = {
        pk for pk in (
            daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id,
            daily_menu.second_course_one_id, daily_menu.second_course_two_id,
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id,
        ) if pk
    }
    eligible_grill = product.component_type == Product.ComponentType.GRILL and product.eligible_for_executive_meal
    if product.pk not in daily_ids and not eligible_grill:
        raise ValidationError("Este producto no puede formar una comida del menú de hoy.")
    clicked_piece = chicken_piece if product.pk == daily_menu.chicken_stew_id else ""
    if product.pk == daily_menu.chicken_stew_id and clicked_piece not in {"leg", "thigh"}:
        raise ValidationError("Selecciona si el pollo es pierna o muslo.")
    add_internal_order_product(
        order=order, product=product, actor=actor, require_individual=False,
        is_package_candidate=True, chicken_piece=clicked_piece,
        raw_option_ids=raw_option_ids, comment=comment,
        daily_menu=daily_menu,
    )
    if not completed_selection:
        return None
    selected = Product.objects.in_bulk(completed_selection[key] for key in ("first", "second", "main"))
    try:
        first = selected[completed_selection["first"]]
        second = selected[completed_selection["second"]]
        main = selected[completed_selection["main"]]
    except KeyError as error:
        raise ValidationError("No encontramos uno de los tiempos elegidos.") from error
    package_type = (
        MealPackage.PackageType.EXECUTIVE
        if main.component_type == Product.ComponentType.GRILL and main.eligible_for_executive_meal
        else MealPackage.PackageType.RUNNING
    )
    package = MealPackage.objects.select_for_update().filter(package_type=package_type, is_active=True).order_by("id").first()
    if not package:
        raise ValidationError("No existe un paquete activo para completar esta comida.")
    final_piece = completed_selection.get("chicken_piece", "") if main.pk == daily_menu.chicken_stew_id else ""
    component_comments = []
    for selected_product in (first, second, main):
        candidate = OrderItem.objects.filter(
            order=order, product=selected_product, is_package_candidate=True,
        ).exclude(customization_comment="").order_by("-id").first()
        if candidate:
            component_comments.append(f"{candidate.product_name_snapshot}: {candidate.customization_comment}")
    if package_comment:
        component_comments.append(package_comment)
    final_comment = " · ".join(component_comments)
    for product_id in (first.pk, second.pk, main.pk):
        _consume_internal_candidate(
            order=order, product_id=product_id,
            actor=actor,
            chicken_product_id=daily_menu.chicken_stew_id, chicken_piece=final_piece,
        )
    cleaned_data = {
        "first_course": first, "second_course": second, "main_course": main,
        "chicken_piece": final_piece, "with_water": with_water,
        "tortillas": "yes" if tortillas else "no", "bread": bread, "beans": "yes" if beans else "no",
        "quantity": 1, "customization_comment": final_comment,
        "egg_product": egg_product,
    }
    return add_internal_order_package(
        order=order, package=package, daily_menu=daily_menu, cleaned_data=cleaned_data,
        merge_identical=False, actor=actor,
    )


@transaction.atomic
def change_internal_order_item(*, order, item, action, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in {Order.Status.PICKED_UP, Order.Status.DELIVERED, Order.Status.CANCELED}:
        raise ValidationError("Este pedido ya no admite modificaciones.")
    item = OrderItem.objects.select_for_update().get(pk=item.pk, order=order)
    if action == "increase":
        _change_order_item_stock(item=item, quantity=1, actor=actor, reserve=True)
        item.quantity += 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    elif action == "decrease" and item.quantity > 1:
        _change_order_item_stock(item=item, quantity=1, actor=actor, reserve=False)
        item.quantity -= 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    elif action in {"decrease", "remove"}:
        _change_order_item_stock(item=item, quantity=item.quantity, actor=actor, reserve=False)
        item.delete()
    else:
        raise ValidationError("La acción solicitada no es válida.")
    recalculate_order_total(order)


@transaction.atomic
def add_internal_order_package(
    *, order, package, daily_menu, cleaned_data, merge_identical=True,
    packaging_quantities=None, actor=None,
):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status in {Order.Status.PICKED_UP, Order.Status.DELIVERED, Order.Status.CANCELED}:
        raise ValidationError("Este pedido ya no admite productos.")
    package = MealPackage.objects.select_for_update().get(pk=package.pk, is_active=True)
    daily_menu = DailyMenu.objects.select_for_update().get(pk=daily_menu.pk, status=DailyMenu.Status.PUBLISHED)
    first, second, main = (cleaned_data[name] for name in ("first_course", "second_course", "main_course"))
    comment = cleaned_data.get("customization_comment", "")
    egg = cleaned_data.get("egg_product")
    unit_price = (package.price_with_water if cleaned_data["with_water"] else package.price_without_water) + (egg.price if egg else Decimal("0"))
    signature = "|".join(map(str, (
        first.pk, second.pk, main.pk, cleaned_data["chicken_piece"],
        int(cleaned_data["with_water"]), cleaned_data["tortillas"], int(cleaned_data.get("bread", False)), cleaned_data["beans"], egg.pk if egg else "", comment.casefold(),
    )))
    item = None
    if merge_identical:
        item = OrderItem.objects.select_for_update().filter(
            order=order, item_type=OrderItem.ItemType.PACKAGE, package=package,
            daily_menu=daily_menu,
            configuration_signature=signature,
        ).first()
    quantity = cleaned_data["quantity"]
    if item:
        item.quantity += quantity
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    else:
        item = OrderItem.objects.create(
            order=order, item_type=OrderItem.ItemType.PACKAGE, package=package,
            daily_menu=daily_menu,
            package_name_snapshot=package.name, first_course=first,
            first_course_name_snapshot=first.name, second_course=second,
            second_course_name_snapshot=second.name, main_course=main,
            main_course_name_snapshot=main.name, chicken_piece=cleaned_data["chicken_piece"],
            with_water=cleaned_data["with_water"],
            water_name_snapshot=daily_menu.water_product.name if cleaned_data["with_water"] else "",
            water_product=daily_menu.water_product if cleaned_data["with_water"] else None,
            tortillas=cleaned_data["tortillas"] == "yes", bread=cleaned_data.get("bread", False), beans=cleaned_data["beans"] == "yes",
            beans_product=daily_menu.beans_order if cleaned_data["beans"] == "yes" else None,
            egg_product=egg, egg_name_snapshot=egg.name if egg else "", egg_price_snapshot=egg.price if egg else Decimal("0"),
            unit_price=unit_price, quantity=quantity, subtotal=unit_price * quantity,
            configuration_signature=signature, customization_comment=comment,
            configuration_snapshot={"comment": comment}, is_customized=bool(comment),
        )
    _change_order_item_stock(item=item, quantity=quantity, actor=actor, reserve=True)
    recalculate_order_total(order)
    for packaging_product, quantity in selected_packaging_products(packaging_quantities or {}):
        for _ in range(quantity):
            add_internal_order_product(
                order=order, product=packaging_product, actor=None,
            )
    return item


@transaction.atomic
def update_internal_order_note(*, order, note):
    # NOTA TEMPORAL PARA APRENDIZAJE: la nota general pertenece al encabezado del
    # pedido; la nota de partida pertenece sólo al producto o paquete elegido.
    # Ambas se actualizan sin reconstruir el ticket. Borra esta nota al leerla.
    order = Order.objects.select_for_update().get(pk=order.pk)
    order.notes = " ".join(note.split())
    order.save(update_fields=("notes", "updated_at"))
    return order


@transaction.atomic
def update_internal_order_item_note(*, order, item, note):
    order = Order.objects.select_for_update().get(pk=order.pk)
    item = OrderItem.objects.select_for_update().get(pk=item.pk, order=order)
    item.customization_comment = " ".join(note.split())
    item.is_customized = bool(item.customization_comment or item.configuration_snapshot)
    item.save(update_fields=("customization_comment", "is_customized"))
    return item


@transaction.atomic
def update_internal_package_extras(*, order, item, cleaned_data, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    # NOTA TEMPORAL PARA APRENDIZAJE: PostgreSQL no permite FOR UPDATE sobre el lado
    # nullable de un OUTER JOIN. Bloqueamos la partida sola y leemos el paquete después.
    item = OrderItem.objects.select_for_update().get(
        pk=item.pk, order=order, item_type=OrderItem.ItemType.PACKAGE,
    )
    if not item.package_id:
        raise ValidationError("El paquete ya no tiene una configuración vigente.")
    package = MealPackage.objects.get(pk=item.package_id)
    _change_order_item_stock(item=item, quantity=item.quantity, actor=actor, reserve=False)
    daily_menu = item.daily_menu or DailyMenu.objects.filter(date=order.operating_date).first()
    item.with_water = cleaned_data["with_water"]
    item.water_name_snapshot = (
        DailyMenu.objects.filter(date=order.operating_date).values_list("water_product__name", flat=True).first() or "Agua del día"
        if item.with_water else ""
    )
    item.water_product = daily_menu.water_product if daily_menu and item.with_water else None
    item.tortillas = cleaned_data["tortillas"]
    item.bread = cleaned_data["bread"]
    item.beans = cleaned_data["beans"]
    item.beans_product = daily_menu.beans_order if daily_menu and item.beans else None
    old_egg_id = item.egg_product_id
    egg = cleaned_data.get("egg_product")
    item.egg_product = egg
    item.egg_name_snapshot = egg.name if egg else ""
    item.egg_price_snapshot = (item.egg_price_snapshot if egg and egg.pk == old_egg_id else egg.price) if egg else Decimal("0")
    item.customization_comment = cleaned_data["customization_comment"]
    item.is_customized = bool(item.customization_comment)
    item.configuration_snapshot = {"comment": item.customization_comment}
    item.configuration_signature = "|".join(map(str, (
        item.first_course_id, item.second_course_id, item.main_course_id,
        item.chicken_piece, int(item.with_water), int(item.tortillas), int(item.bread), int(item.beans),
        item.customization_comment.casefold(), item.pk,
    )))
    item.unit_price = (package.price_with_water if item.with_water else package.price_without_water) + item.egg_price_snapshot
    item.subtotal = item.unit_price * item.quantity
    item.save(update_fields=(
        "with_water", "water_name_snapshot", "water_product", "tortillas", "bread", "beans", "beans_product",
        "egg_product", "egg_name_snapshot", "egg_price_snapshot",
        "customization_comment", "is_customized", "configuration_snapshot",
        "configuration_signature", "unit_price", "subtotal",
    ))
    _change_order_item_stock(item=item, quantity=item.quantity, actor=actor, reserve=True)
    recalculate_order_total(order)
    return item


@transaction.atomic
def add_water_to_internal_package(*, order, water_product, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    daily_menu = DailyMenu.objects.filter(
        date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
        water_product=water_product,
    ).first()
    if not daily_menu:
        return None
    item = OrderItem.objects.select_for_update().select_related("package").filter(
        order=order, item_type=OrderItem.ItemType.PACKAGE, with_water=False,
    ).order_by("id").first()
    if not item or not item.package:
        return None
    _change_order_item_stock(item=item, quantity=item.quantity, actor=actor, reserve=False)
    item.with_water = True
    item.water_name_snapshot = water_product.name
    item.water_product = water_product
    item.unit_price = item.package.price_with_water
    item.subtotal = item.unit_price * item.quantity
    item.configuration_signature = f"{item.configuration_signature}|agua:{item.pk}"
    item.save(update_fields=(
        "with_water", "water_name_snapshot", "water_product", "unit_price", "subtotal", "configuration_signature",
    ))
    _change_order_item_stock(item=item, quantity=item.quantity, actor=actor, reserve=True)
    recalculate_order_total(order)
    return item


def available_order_actions(order):
    if order.status == Order.Status.PENDING_CONFIRMATION:
        return ("confirm", "cancel")
    if order.status in {Order.Status.CONFIRMED, Order.Status.SCHEDULED}:
        return ("start_preparing",)
    if order.status == Order.Status.PREPARING:
        return ("mark_ready",)
    if order.status == Order.Status.READY and order.order_type == Order.OrderType.PICKUP:
        return ("complete_pickup",)
    if order.status == Order.Status.READY and order.order_type == Order.OrderType.DELIVERY:
        return ("dispatch_delivery",)
    if order.status == Order.Status.OUT_FOR_DELIVERY:
        return ("complete_delivery",)
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
            item_daily_menu = DailyMenu.objects.filter(
                date=order.operating_date, status=DailyMenu.Status.PUBLISHED,
            ).first()
            if item_daily_menu and product.pk not in _daily_product_ids(item_daily_menu):
                item_daily_menu = None
            order_item = OrderItem.objects.create(
                order=order, item_type=OrderItem.ItemType.PRODUCT, product=product,
                daily_menu=item_daily_menu,
                product_name_snapshot=product.name, unit_price=item["unit_price"],
                configuration_snapshot=item["configuration"]["snapshot"],
                configuration_signature=item["configuration"]["signature"],
                customization_comment=" · ".join(filter(None, (item["configuration"]["comment"], item.get("item_note", "")))),
                is_customized=bool(item["configuration"]["is_customized"] or item.get("item_note")),
                quantity=item["quantity"], subtotal=item["subtotal"],
                tortillas=False, beans=False,
            )
        else:
            order_item = OrderItem.objects.create(
                order=order, item_type=OrderItem.ItemType.PACKAGE, package=item["package"],
                daily_menu=item["daily_menu"],
                package_name_snapshot=item["package"].name,
                first_course=item["first_course"], first_course_name_snapshot=item["first_course"].name,
                second_course=item["second_course"], second_course_name_snapshot=item["second_course"].name,
                main_course=item["main_course"], main_course_name_snapshot=item["main_course"].name,
                chicken_piece=item["chicken_piece"], with_water=item["with_water"],
                water_name_snapshot=item["daily_menu"].water_product.name if item["with_water"] else "",
                water_product=item["daily_menu"].water_product if item["with_water"] else None,
                tortillas=item["tortillas"], beans=item["beans"], unit_price=item["unit_price"],
                beans_product=item["daily_menu"].beans_order if item["beans"] else None,
                quantity=item["quantity"], subtotal=item["subtotal"],
                customization_comment=item.get("item_note", ""), is_customized=bool(item.get("item_note")),
            )
        _change_order_item_stock(
            item=order_item, quantity=order_item.quantity, actor=None, reserve=True,
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
    item = OrderItem.objects.create(
        order=order,
        daily_menu=daily_menu,
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
        water_product=daily_menu.water_product if cleaned_data["with_water"] else None,
        tortillas=cleaned_data["tortillas"] == "yes",
        beans=cleaned_data["beans"] == "yes",
        beans_product=daily_menu.beans_order if cleaned_data["beans"] == "yes" else None,
        unit_price=total,
        subtotal=total,
    )
    _change_order_item_stock(item=item, quantity=1, actor=None, reserve=True)
    return order


@transaction.atomic
def change_internal_order_type(*, order, order_type, actor):
    if order_type not in Order.OrderType.values:
        raise ValidationError("Selecciona una modalidad válida.")
    order = Order.objects.select_for_update().get(pk=order.pk)
    old_type = order.order_type
    if old_type == order_type:
        return order
    order.order_type = order_type
    order.save(update_fields=("order_type", "updated_at"))
    _move_order_stock_channel(order=order, old_type=old_type, actor=actor)
    return order


@transaction.atomic
def transition_order(*, order, action, actor=None):
    order = Order.objects.select_for_update().get(pk=order.pk)
    # NOTA TEMPORAL PARA APRENDIZAJE: las reglas críticas viven también en el
    # servicio central. Así ninguna vista futura puede habilitar accidentalmente
    # Reiniciar para Telefonista ni Entregado para Repartidor. Borra esta nota.
    if action == "restart_cycle" and not user_has_any_role(actor, (ADMIN,)):
        raise ValidationError("Sólo un administrador puede reiniciar el ciclo del pedido.")
    if action == "cancel" and not user_has_any_role(actor, (ADMIN,)):
        raise ValidationError("Sólo un administrador puede cancelar pedidos.")
    transitions = {
        (Order.Status.PENDING_CONFIRMATION, "cancel"): Order.Status.CANCELED,
        (Order.Status.CONFIRMED, "start_preparing"): Order.Status.PREPARING,
        (Order.Status.SCHEDULED, "start_preparing"): Order.Status.PREPARING,
        (Order.Status.PREPARING, "mark_ready"): Order.Status.READY,
        (Order.Status.READY, "complete_pickup"): Order.Status.PICKED_UP,
        (Order.Status.READY, "dispatch_delivery"): Order.Status.OUT_FOR_DELIVERY,
        (Order.Status.OUT_FOR_DELIVERY, "complete_delivery"): Order.Status.DELIVERED,
        (Order.Status.PICKED_UP, "restart_cycle"): Order.Status.PENDING_CONFIRMATION,
        (Order.Status.DELIVERED, "restart_cycle"): Order.Status.PENDING_CONFIRMATION,
    }
    if action == "cancel" and order.status not in {
        Order.Status.CANCELED, Order.Status.PICKED_UP, Order.Status.DELIVERED,
    }:
        target_status = Order.Status.CANCELED
    else:
        target_status = (
            scheduled_initial_status(order)
            if order.status == Order.Status.PENDING_CONFIRMATION and action == "confirm"
            else transitions.get((order.status, action))
        )
    if not target_status:
        raise ValidationError("Ese cambio no está permitido desde el estado actual.")
    if action == "complete_pickup" and order.order_type != Order.OrderType.PICKUP:
        raise ValidationError("Solo un pedido para recoger puede marcarse como recogido.")
    if action == "complete_pickup":
        if not order.payment_method:
            raise ValidationError("Registra la forma de pago antes de cerrar completamente el ticket.")
        if order.payment_method == Order.PaymentMethod.CASH and order.needs_change and (
            order.cash_tendered is None or order.cash_tendered < order.total
        ):
            raise ValidationError("Actualiza el efectivo recibido antes de cerrar el ticket.")
    if action == "complete_delivery" and order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("Solo un pedido de entrega puede marcarse como entregado.")
    if action == "dispatch_delivery" and order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("Solo un pedido a domicilio puede pasar a reparto.")
    if action == "dispatch_delivery" and order.delivery_person_id is None:
        raise ValidationError("Asigna un repartidor antes de marcar la salida.")
    if action == "dispatch_delivery":
        can_dispatch = user_has_any_role(actor, (ADMIN, ORDER_TAKER))
        if not can_dispatch:
            raise ValidationError("Sólo Administrador o Telefonista pueden iniciar este reparto.")
    if action == "complete_delivery":
        if order.delivery_person_id is None:
            raise ValidationError("Primero debes asignar el pedido a un repartidor.")
        can_complete = (
            actor == order.delivery_person
            or user_has_any_role(actor, (ADMIN, ORDER_TAKER))
        )
        if not can_complete:
            raise ValidationError("Sólo Administrador, Telefonista o el repartidor asignado pueden completar esta entrega.")
    if order.attention_started_at is None and actor is not None:
        order.attention_started_at = timezone.now()
        order.attention_started_by = actor
    previous_status = order.status
    if action == "cancel":
        for item in order.items.select_for_update().all():
            _change_order_item_stock(
                item=item, quantity=item.quantity, actor=actor, reserve=False,
            )
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
    if target_status in {Order.Status.PICKED_UP, Order.Status.DELIVERED}:
        StockMovement.objects.filter(
            reference_type="order_item",
            reference_id__in=order.items.values_list("pk", flat=True),
            reason=StockMovement.Reason.RESERVATION,
        ).update(reason=StockMovement.Reason.CONSUMPTION)
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
    if order.delivery_tip_amount > 0:
        order.delivery_tip_recipient = delivery_person
    order.save(update_fields=[
        "delivery_person", "delivery_assigned_by", "delivery_assigned_at",
        "delivery_tip_recipient", "updated_at",
    ])
    return order


@transaction.atomic
def update_delivery_tip(*, order, amount, actor):
    # NOTA TEMPORAL PARA APRENDIZAJE: efectivo no se registra aquí porque el cliente
    # entrega esa propina directamente. Terminal/Transferencia sí pasan por el negocio
    # y deben quedar como deuda a favor del repartidor asignado. Borra esta nota.
    # NOTA TEMPORAL PARA APRENDIZAJE: delivery_person es opcional. PostgreSQL no
    # permite FOR UPDATE sobre el lado nullable de un OUTER JOIN, así que bloqueamos
    # únicamente Order y Django lee el repartidor aparte si hace falta. Borra esta nota.
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.order_type != Order.OrderType.DELIVERY:
        raise ValidationError("La propina de reparto sólo aplica a entregas a domicilio.")
    if order.payment_method not in {Order.PaymentMethod.CARD, Order.PaymentMethod.TRANSFER}:
        raise ValidationError("La propina registrada sólo aplica a pagos con Terminal o Transferencia.")
    order.delivery_tip_amount = amount
    order.delivery_tip_recipient = order.delivery_person if amount > 0 else None
    order.delivery_tip_updated_by = actor
    order.delivery_tip_updated_at = timezone.now()
    order.save(update_fields=(
        "delivery_tip_amount", "delivery_tip_recipient", "delivery_tip_updated_by",
        "delivery_tip_updated_at", "updated_at",
    ))
    return order
