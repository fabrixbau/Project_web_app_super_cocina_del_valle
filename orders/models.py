# NOTA TEMPORAL PARA APRENDIZAJE:
# OrderItem ahora distingue paquetes y productos individuales para soportar el carrito.
# Order representa el encabezado del pedido (cliente, entrega, pago y estado). OrderItem
# conserva una fotografía del paquete elegido para que el historial no cambie si mañana
# editamos el menú o los precios. DailyOrderCounter genera folios diarios seguros.
# Borra esta nota después de leerla.

import uuid

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from menu.models import MealPackage, Product


class DailyOrderCounter(models.Model):
    operating_date = models.DateField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.operating_date}: {self.last_number}"


class Order(models.Model):
    class OrderType(models.TextChoices):
        PICKUP = "pickup", "Recoger en la fonda"
        DELIVERY = "delivery", "Entrega a domicilio"

    class Source(models.TextChoices):
        PUBLIC_WEB = "public_web", "Portal público"
        INTERNAL = "internal", "Captura interna"

    class Status(models.TextChoices):
        PENDING_CONFIRMATION = "pending_confirmation", "Pendiente de confirmar"
        CONFIRMED = "confirmed", "Confirmado"
        PREPARING = "preparing", "En preparación"
        READY = "ready", "Listo"
        OUT_FOR_DELIVERY = "out_for_delivery", "En reparto"
        DELIVERED = "delivered", "Entregado"
        CANCELED = "canceled", "Cancelado"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"

    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    daily_number = models.PositiveIntegerField(editable=False)
    operating_date = models.DateField(default=timezone.localdate)
    order_type = models.CharField(max_length=20, choices=OrderType.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.PUBLIC_WEB)
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
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    needs_change = models.BooleanField(default=False)
    cash_tendered = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(
            fields=["operating_date", "daily_number"], name="unique_daily_order_number"
        )]

    def __str__(self):
        return f"#{self.daily_number:03d} · {self.operating_date}"

    @property
    def formatted_number(self):
        return f"#{self.daily_number:03d}"

    @property
    def change_required(self):
        if self.needs_change and self.cash_tendered is not None:
            return self.cash_tendered - self.total
        return None


class OrderItem(models.Model):
    class ItemType(models.TextChoices):
        PACKAGE = "package", "Paquete"
        PRODUCT = "product", "Producto individual"

    class ChickenPiece(models.TextChoices):
        LEG = "leg", "Pierna"
        THIGH = "thigh", "Muslo"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.PACKAGE)
    package = models.ForeignKey(
        MealPackage, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items"
    )
    package_name_snapshot = models.CharField(max_length=100, blank=True)
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="individual_order_items"
    )
    product_name_snapshot = models.CharField(max_length=150, blank=True)
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
