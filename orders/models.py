# NOTA TEMPORAL PARA APRENDIZAJE:
# Este bloque también guarda repartidor, quién lo asignó y hora de asignación del pedido.
# Registramos quién inició la atención; pago puede quedar vacío para recoger. El ciclo de
# estados puede reiniciarse sin borrar el historial. Borra esta nota después de leerla.
# Order representa el encabezado del pedido (cliente, entrega, pago y estado). OrderItem
# conserva una fotografía del paquete elegido para que el historial no cambie si mañana
# editamos el menú o los precios. DailyOrderCounter genera folios diarios seguros.
# Borra esta nota después de leerla.
# Las partidas individuales guardan configuración, firma y bandera Modificado como snapshot;
# no dependen de que la receta futura conserve las mismas opciones. Borra esta nota.
# El valor interno `card` se conserva para no romper pedidos anteriores, pero su nombre
# visible es Terminal porque el cobro se realiza presencialmente, no en línea. Borra esta nota.

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from menu.models import DailyMenu, MealPackage, Product


class DailyOrderCounter(models.Model):
    operating_date = models.DateField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.operating_date}: {self.last_number}"


class Customer(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE: Customer guarda a la persona una sola vez;
    # sus domicilios viven en CustomerAddress porque un cliente puede pedir desde
    # más de una dirección. Borra esta nota después de leerla.
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    phone_key = models.CharField(max_length=30, blank=True, db_index=True, editable=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.phone_key = "".join(character for character in self.phone if character.isdigit())
        if kwargs.get("update_fields") and "phone" in kwargs["update_fields"]:
            kwargs["update_fields"] = (*kwargs["update_fields"], "phone_key")
        return super().save(*args, **kwargs)


class CustomerAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
    street = models.CharField(max_length=150)
    exterior_number = models.CharField(max_length=20)
    interior_number = models.CharField(max_length=20, blank=True)
    neighborhood = models.CharField(max_length=150, blank=True)
    references = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "id")

    def __str__(self):
        return f"{self.street} {self.exterior_number}"


class Order(models.Model):
    class OrderType(models.TextChoices):
        PICKUP = "pickup", "Recoger en la fonda"
        DELIVERY = "delivery", "Entrega a domicilio"

    class Source(models.TextChoices):
        PUBLIC_WEB = "public_web", "Portal público"
        INTERNAL = "internal", "Captura interna"

    class Status(models.TextChoices):
        DRAFT = "draft", "Capturando"
        PENDING_CONFIRMATION = "pending_confirmation", "Pendiente de confirmar"
        CONFIRMED = "confirmed", "Confirmado"
        SCHEDULED = "scheduled", "Programado"
        PREPARING = "preparing", "En preparación"
        READY = "ready", "Listo"
        OUT_FOR_DELIVERY = "out_for_delivery", "En reparto"
        PICKED_UP = "picked_up", "Recogido"
        DELIVERED = "delivered", "Entregado"
        CANCELED = "canceled", "Cancelado"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Terminal"
        TRANSFER = "transfer", "Transferencia"

    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    daily_number = models.PositiveIntegerField(editable=False)
    operating_date = models.DateField(default=timezone.localdate)
    order_type = models.CharField(max_length=20, choices=OrderType.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PUBLIC_WEB)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="internal_orders_created",
    )
    agenda_customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders",
    )
    agenda_address = models.ForeignKey(
        CustomerAddress, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders",
    )
    requested_for = models.DateTimeField("hora solicitada", null=True, blank=True)
    requested_date = models.DateField("fecha solicitada", null=True, blank=True)
    requested_time = models.TimeField("hora solicitada", null=True, blank=True)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDING_CONFIRMATION
    )
    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30)
    street = models.CharField(max_length=150, blank=True)
    exterior_number = models.CharField(max_length=20, blank=True)
    interior_number = models.CharField(max_length=20, blank=True)
    neighborhood = models.CharField(max_length=150, blank=True)
    references = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    needs_change = models.BooleanField(default=False)
    cash_tendered = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    # NOTA TEMPORAL PARA APRENDIZAJE: estos campos no calculan el cambio; registran
    # que el repartidor ya lo devolvió o concilió con Caja al cierre. Así distinguimos
    # el monto solicitado de su conciliación real. Borra esta nota al leerla.
    cash_settlement_confirmed = models.BooleanField(default=False)
    cash_settlement_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cash_settlements_confirmed",
    )
    cash_settlement_at = models.DateTimeField(null=True, blank=True)
    # NOTA TEMPORAL PARA APRENDIZAJE: liberar en Caja sólo retira el pedido de su
    # bandeja. No cambia el estado de preparación o reparto, porque son procesos
    # independientes. Borra esta nota después de leerla.
    cashier_released_at = models.DateTimeField(null=True, blank=True)
    cashier_released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cashier_orders_released",
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    # NOTA TEMPORAL PARA APRENDIZAJE: la propina de reparto no modifica el consumo.
    # Se guarda aparte para saber cuánto devolver al repartidor cuando el restaurante
    # la cobró por Terminal o Transferencia. Borra esta nota después de leerla.
    delivery_tip_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
    )
    delivery_tip_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="delivery_tips_received",
    )
    delivery_tip_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="delivery_tips_updated",
    )
    delivery_tip_updated_at = models.DateTimeField(null=True, blank=True)
    attention_started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders_attention_started",
    )
    attention_started_at = models.DateTimeField(null=True, blank=True)
    delivery_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_delivery_orders",
    )
    delivery_assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="delivery_assignments_made",
    )
    delivery_assigned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(
            fields=["operating_date", "daily_number"], name="unique_daily_order_number"
        )]

    def __str__(self):
        return f"#{self.formatted_number} · {self.operating_date}"

    @property
    def formatted_number(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: el consecutivo sigue guardándose como
        # un número sencillo que reinicia cada día. Aquí sólo construimos el
        # folio visible uniendo día + mes + consecutivo. Borra esta nota al leerla.
        return f"{self.operating_date:%d%m}{self.daily_number:03d}"

    @property
    def change_required(self):
        if self.needs_change and self.cash_tendered is not None:
            return self.cash_tendered - self.total
        return None

    @property
    def total_with_delivery_tip(self):
        return self.total + self.delivery_tip_amount

    @property
    def is_advance_order(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: el horario solicitado y el avance de cocina
        # son conceptos separados. Esta propiedad conserva la clasificación original.
        # Borra esta nota después de leerla.
        if not self.requested_for or not self.created_at:
            return False
        return self.requested_for >= self.created_at + timedelta(hours=1)

    @property
    def timing_label(self):
        if self.is_advance_order:
            return f"Programado · {timezone.localtime(self.requested_for):%d/%m %H:%M}"
        return "Lo antes posible"


class OrderItem(models.Model):
    class ItemType(models.TextChoices):
        PACKAGE = "package", "Paquete"
        PRODUCT = "product", "Producto individual"

    class ChickenPiece(models.TextChoices):
        LEG = "leg", "Pierna"
        THIGH = "thigh", "Muslo"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    daily_menu = models.ForeignKey(
        DailyMenu, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_items",
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.PACKAGE)
    is_package_candidate = models.BooleanField(default=False)
    package = models.ForeignKey(
        MealPackage, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items"
    )
    package_name_snapshot = models.CharField(max_length=100, blank=True)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="individual_order_items"
    )
    product_name_snapshot = models.CharField(max_length=150, blank=True)
    configuration_snapshot = models.JSONField(default=list, blank=True)
    configuration_signature = models.CharField(max_length=500, blank=True)
    customization_comment = models.CharField(max_length=150, blank=True)
    is_customized = models.BooleanField(default=False)
    first_course = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items_as_first_course"
    )
    first_course_name_snapshot = models.CharField(max_length=150, blank=True)
    second_course = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items_as_second_course"
    )
    second_course_name_snapshot = models.CharField(max_length=150, blank=True)
    main_course = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items_as_main_course"
    )
    main_course_name_snapshot = models.CharField(max_length=150, blank=True)
    chicken_piece = models.CharField(max_length=20, choices=ChickenPiece.choices, blank=True)
    with_water = models.BooleanField(default=False)
    water_name_snapshot = models.CharField(max_length=150, blank=True)
    water_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_items_as_water",
    )
    tortillas = models.BooleanField()
    bread = models.BooleanField(default=False)
    beans = models.BooleanField()
    beans_product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_items_as_beans",
    )
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    def __str__(self):
        if self.item_type == self.ItemType.PRODUCT:
            return f"{self.product_name_snapshot} × {self.quantity}"
        return f"{self.package_name_snapshot} × {self.quantity}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30, choices=Order.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_status_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]

    def __str__(self):
        return f"{self.order} · {self.get_to_status_display()}"


class TerminalCut(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE: el corte agrupa los movimientos reales de una
    # terminal y un día. Es conciliación, no una segunda fuente de ventas o propinas.
    # Borra esta nota después de leerla.
    class Provider(models.TextChoices):
        CLOVER = "clover", "Clover"
        MERCADO_PAGO = "mercado_pago", "Mercado Pago"
        TRANSFER = "transfer", "Transferencias"

    class Status(models.TextChoices):
        OPEN = "open", "Abierto"
        CLOSED = "closed", "Cerrado"

    operating_date = models.DateField(default=timezone.localdate)
    provider = models.CharField(max_length=30, choices=Provider.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="terminal_cuts_closed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-operating_date", "provider")
        constraints = [models.UniqueConstraint(
            fields=("operating_date", "provider"), name="unique_terminal_cut_date_provider",
        )]

    def __str__(self):
        return f"{self.get_provider_display()} · {self.operating_date:%d/%m/%Y}"


class TerminalMovement(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE: consumption_amount no se almacena: siempre se
    # calcula del total menos propina, evitando datos contradictorios. Borra esta nota.
    cut = models.ForeignKey(TerminalCut, on_delete=models.CASCADE, related_name="movements")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    tip_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="terminal_movements_received",
    )
    terminal_name_reference = models.CharField(max_length=150, blank=True)
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="terminal_movements",
    )
    table_account = models.ForeignKey(
        "tables.TableAccount", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="terminal_movements",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="terminal_movements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("order",), condition=models.Q(order__isnull=False),
                name="unique_terminal_movement_order",
            ),
            models.UniqueConstraint(
                fields=("table_account",), condition=models.Q(table_account__isnull=False),
                name="unique_terminal_movement_table",
            ),
        ]

    @property
    def consumption_amount(self):
        return self.total_amount - self.tip_amount

    def __str__(self):
        return f"{self.cut} · ${self.total_amount}"


class CustomerDebt(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE: el estado de cobro vive separado del estado
    # operativo. Un pedido puede estar Entregado y conservar aquí un saldo pendiente
    # sin alterar la bitácora de cocina o reparto. Borra esta nota después de leerla.
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PARTIAL = "partial", "Pago parcial"
        PAID = "paid", "Pagado"
        FORGIVEN = "forgiven", "Condonado"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="debts")
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="customer_debt")
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING, db_index=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_debts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("status", "-created_at")
        indexes = [models.Index(fields=("customer", "status"), name="debt_customer_status_idx")]

    @property
    def balance(self):
        return max(self.original_amount - self.paid_amount, 0)

    def __str__(self):
        return f"{self.customer} · {self.order.formatted_number} · ${self.balance}"


class CustomerDebtMovement(models.Model):
    # Cada cambio financiero queda como renglón independiente para conocer quién
    # registró un abono, condonó o reabrió la cuenta. Borra esta nota al leerla.
    class Action(models.TextChoices):
        PAYMENT = "payment", "Abono"
        FORGIVE = "forgive", "Condonación"
        REOPEN = "reopen", "Reapertura"

    debt = models.ForeignKey(CustomerDebt, on_delete=models.CASCADE, related_name="movements")
    action = models.CharField(max_length=15, choices=Action.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=Order.PaymentMethod.choices, blank=True)
    note = models.CharField(max_length=250, blank=True)
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_debt_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.debt} · {self.get_action_display()}"
