# NOTA TEMPORAL PARA APRENDIZAJE:
# `is_package_candidate` separa productos por orden de tiempos que esperan formar paquete.
# Al cerrar una cuenta guardamos una fotografía del cobro, propina, cambio y responsables;
# así el historial no cambia aunque después se editen precios. Borra esta nota al terminar.
# Los paquetes guardan referencias opcionales a sus tres tiempos y `is_complete`; esto
# permite capturarlos progresivamente y editarlos desde el ticket sin perder snapshots.
# `daily_menu` conserva además el menú que originó la partida para poder terminarla otro día.
# TableAccountItem fotografía productos y paquetes completos; TableCommand queda compatible.
# DiningTable representa una mesa física. TableAccount representa una visita/cuenta y
# conserva mesa, mesero responsable, quién la abrió y sus horas. Fila y columna colocan
# cada mesa en el mapa físico; la restricción impide
# tener dos cuentas abiertas simultáneamente en la misma mesa. Borra esta nota al terminar.
# Productos personalizados guardan snapshot, firma y `is_customized`; esto separa recetas
# distintas del mismo producto y conserva la comanda histórica. Borra esta nota.
# En pagos conservamos el código histórico `card`, pero mostramos Terminal para aclarar
# que el negocio cobra con un dispositivo físico y no mediante la app. Borra esta nota.

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class DiningTable(models.Model):
    name = models.CharField("nombre", max_length=60, unique=True)
    display_order = models.PositiveIntegerField("orden visual", default=0)
    map_row = models.PositiveSmallIntegerField("fila en mapa", default=1)
    map_column = models.PositiveSmallIntegerField("columna en mapa", default=1)
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("display_order", "name")
        verbose_name = "mesa"
        verbose_name_plural = "mesas"

    def __str__(self):
        return self.name


class TableAccount(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # El nombre pertenece a esta visita/cuenta y es opcional; no identifica permanentemente a
    # una persona ni cambia el nombre de la mesa. Se usa para localizarla en historial. Borra la nota.
    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Terminal"
        TRANSFER = "transfer", "Transferencia"

    table = models.ForeignKey(DiningTable, on_delete=models.PROTECT, related_name="accounts")
    customer_name = models.CharField("nombre del cliente", max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    assigned_waiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_table_accounts",
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="opened_table_accounts",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="closed_table_accounts",
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, blank=True)
    subtotal_closed = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tip_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
    )
    tip_recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="table_tips_received",
    )
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cash_tendered = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    change_given = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("-opened_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("table",), condition=Q(status="open"),
                name="unique_open_account_per_table",
            ),
        ]
        verbose_name = "cuenta de mesa"
        verbose_name_plural = "cuentas de mesa"

    def __str__(self):
        return f"{self.table} · {self.get_status_display()}"


class TableActivity(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # Esta bitácora no reemplaza al mesero responsable: guarda quién ejecutó cada cambio.
    # Así la propina sigue perteneciendo al responsable aunque otro mesero apoye. Borra esta nota.
    class Action(models.TextChoices):
        OPEN = "open", "Abrió la mesa"
        ADD = "add", "Agregó producto"
        CUSTOMIZE = "customize", "Agregó producto modificado"
        INCREASE = "increase", "Aumentó cantidad"
        DECREASE = "decrease", "Disminuyó cantidad"
        REMOVE = "remove", "Eliminó partida"
        PACKAGE = "package", "Agregó paquete"
        PACKAGE_EDIT = "package_edit", "Editó paquete"
        REASSIGN = "reassign", "Cambió responsable"
        CUSTOMER = "customer", "Actualizó cliente"
        CLOSE = "close", "Cobró y cerró"

    account = models.ForeignKey(TableAccount, on_delete=models.CASCADE, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="table_activities")
    action = models.CharField(max_length=20, choices=Action.choices)
    description = models.CharField(max_length=255, blank=True)
    quantity_delta = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        indexes = [models.Index(fields=("account", "created_at"), name="table_act_account_time")]
        verbose_name = "movimiento de mesa"
        verbose_name_plural = "movimientos de mesa"


class TableCommand(models.Model):
    account = models.ForeignKey(TableAccount, on_delete=models.CASCADE, related_name="commands")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="table_commands_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")
        verbose_name = "comanda de mesa"
        verbose_name_plural = "comandas de mesa"

    def __str__(self):
        return f"{self.account.table} · {self.created_at:%H:%M}"


class TableAccountItem(models.Model):
    class ItemType(models.TextChoices):
        PRODUCT = "product", "Producto"
        PACKAGE = "package", "Paquete"

    account = models.ForeignKey(TableAccount, on_delete=models.CASCADE, related_name="items")
    command = models.ForeignKey(
        TableCommand, on_delete=models.CASCADE, null=True, blank=True, related_name="items",
    )
    product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_account_items",
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.PRODUCT)
    is_package_candidate = models.BooleanField(default=False)
    package = models.ForeignKey(
        "menu.MealPackage", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_account_items",
    )
    daily_menu = models.ForeignKey(
        "menu.DailyMenu", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_account_items",
    )
    package_name_snapshot = models.CharField(max_length=100, blank=True)
    first_course_product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_items_as_first_course",
    )
    second_course_product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_items_as_second_course",
    )
    main_course_product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_items_as_main_course",
    )
    first_course_snapshot = models.CharField(max_length=150, blank=True)
    second_course_snapshot = models.CharField(max_length=150, blank=True)
    main_course_snapshot = models.CharField(max_length=150, blank=True)
    chicken_piece = models.CharField(max_length=20, blank=True)
    with_water = models.BooleanField(default=False)
    water_name_snapshot = models.CharField(max_length=150, blank=True)
    water_product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_items_as_water",
    )
    tortillas = models.BooleanField(default=False)
    beans = models.BooleanField(default=False)
    beans_product = models.ForeignKey(
        "menu.Product", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="table_items_as_beans",
    )
    refill_extra = models.BooleanField(default=False)
    is_complete = models.BooleanField(default=True)
    product_name_snapshot = models.CharField(max_length=150)
    configuration_snapshot = models.JSONField(default=list, blank=True)
    configuration_signature = models.CharField(max_length=500, blank=True)
    customization_comment = models.CharField(max_length=150, blank=True)
    is_customized = models.BooleanField(default=False)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="table_items_added",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("added_at", "id")
        verbose_name = "consumo de mesa"
        verbose_name_plural = "consumos de mesa"

    def __str__(self):
        return f"{self.quantity} × {self.product_name_snapshot}"
