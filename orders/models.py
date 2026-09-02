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

from menu.models import MealPackage, Product


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
    # que Caja ya entregó físicamente ese cambio al repartidor. Así distinguimos lo
    # solicitado por el cliente de la entrega real de dinero. Borra esta nota al leerla.
    cash_handoff_confirmed = models.BooleanField(default=False)
    cash_handoff_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cash_handoffs_confirmed",
    )
    cash_handoff_at = models.DateTimeField(null=True, blank=True)
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
    tortillas = models.BooleanField()
    beans = models.BooleanField()
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
