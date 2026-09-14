# NOTA TEMPORAL PARA APRENDIZAJE:
# Category ahora permite ordenar y mostrar secciones de mesa de forma distinta durante
# desayunos y comida. Es configuración, no nombres hardcodeados. Borra esta nota al leerla.
# El menú diario puede enlazar una orden de frijoles opcional que nunca cuenta como tiempo.
# Categorías también guardan orden y visibilidad públicos separados para desayuno/comida.
# Los grupos de personalización pertenecen a un producto y contienen opciones estándar o
# alternativas. Al copiarlos se crean registros independientes para poder ajustarlos después.
# Borra esta nota cuando termines de revisar este bloque.

from django.core.exceptions import ValidationError
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class ServicePeriod(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=80, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "start_time"]
        verbose_name = "periodo de servicio"
        verbose_name_plural = "periodos de servicio"

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    def contains(self, current_time):
        return self.is_active and self.start_time <= current_time <= self.end_time


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to="menu/categories/", blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    public_breakfast_order = models.PositiveIntegerField("orden público en desayunos", default=0)
    public_lunch_order = models.PositiveIntegerField("orden público en comida", default=0)
    table_breakfast_order = models.PositiveIntegerField("orden en desayunos", default=0)
    table_lunch_order = models.PositiveIntegerField("orden en comida", default=0)
    show_on_public_breakfast = models.BooleanField("mostrar al cliente en desayunos", default=True)
    show_on_public_lunch = models.BooleanField("mostrar al cliente en comida", default=True)
    show_on_table_breakfast = models.BooleanField("mostrar en modo desayunos", default=True)
    show_on_table_lunch = models.BooleanField("mostrar en modo comida", default=True)
    show_table_packages = models.BooleanField(
        "mostrar paquetes de mesa al elegirla", default=False,
        help_text="Actívalo en la categoría que debe abrir Comida corrida y ejecutiva.",
    )

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.name


class Product(models.Model):
    class PackagingKind(models.TextChoices):
        NONE = "none", "No es envase"
        PACKAGE = "package", "Paquete de envases"
        INDIVIDUAL = "individual", "Envase individual"
        CUSTOMER_OWN = "customer_own", "Cliente trae recipientes"

    class ComponentType(models.TextChoices):
        GENERAL = "general", "Producto general"
        CHICKEN_CONSOMME = "chicken_consomme", "Consomé de pollo"
        VARIABLE_FIRST_COURSE = "variable_first_course", "Primer tiempo variable"
        SECOND_COURSE = "second_course", "Segundo tiempo (arroz o espagueti)"
        CHICKEN_STEW = "chicken_stew", "Guisado de pollo"
        BEEF_STEW = "beef_stew", "Guisado de res"
        VARIED_STEW = "varied_stew", "Guisado variado"
        GRILL = "grill", "Producto de plancha"
        BEVERAGE = "beverage", "Bebida"
        DAILY_WATER = "daily_water", "Agua del menú diario"
        COMPLEMENT = "complement", "Complemento"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu/products/", blank=True)
    image_position_x = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    image_position_y = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])
    image_zoom = models.DecimalField(max_digits=3, decimal_places=2, default=1, validators=[MinValueValidator(1), MaxValueValidator(3)])
    is_available = models.BooleanField(default=True)
    component_type = models.CharField(
        max_length=30,
        choices=ComponentType.choices,
        default=ComponentType.GENERAL,
    )
    service_periods = models.ManyToManyField(ServicePeriod, blank=True, related_name="products")
    is_sold_individually = models.BooleanField(default=True)
    uses_bread_stock = models.BooleanField(default=False, help_text="Descuenta una unidad del conteo diario de bolillos por cada unidad vendida.")
    eligible_for_executive_meal = models.BooleanField(default=False)
    packaging_kind = models.CharField(
        "tipo de envase",
        max_length=20,
        choices=PackagingKind.choices,
        default=PackagingKind.NONE,
        db_index=True,
        help_text="Los envases aparecen en una barra rápida exclusiva para Mesas y Pedidos.",
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__sort_order", "category__name", "sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "name"], name="unique_product_name_per_category")
        ]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def __str__(self):
        return f"{self.category.name} · {self.name}"


class ProductOptionGroup(models.Model):
    class SelectionType(models.TextChoices):
        SINGLE = "single", "Elegir una opción"
        MULTIPLE = "multiple", "Elegir varias opciones"

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="option_groups",
    )
    shared_key = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    name = models.CharField(max_length=100)
    selection_type = models.CharField(
        max_length=20, choices=SelectionType.choices, default=SelectionType.MULTIPLE,
    )
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("product", "name"), name="unique_product_option_group_name",
            ),
            models.UniqueConstraint(
                fields=("product", "shared_key"), name="unique_product_shared_option_group",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} · {self.name}"


class ProductOption(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # Las opciones con la misma clave de sustitución son equivalentes entre sí. Por ejemplo,
    # crema y mayonesa pueden usar "Aderezo": al elegir una se reemplaza la otra. Borra esta nota.
    group = models.ForeignKey(
        ProductOptionGroup, on_delete=models.CASCADE, related_name="options",
    )
    name = models.CharField(max_length=100)
    price_adjustment = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)],
    )
    is_default = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    replacement_pair = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("group", "name"), name="unique_product_option_name",
            ),
        ]

    def __str__(self):
        return f"{self.group.name} · {self.name}"


class DailyMenu(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PUBLISHED = "published", "Publicado"
        CLOSED = "closed", "Cerrado"

    date = models.DateField(unique=True, default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    water_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_water",
        limit_choices_to={"component_type": Product.ComponentType.DAILY_WATER},
    )
    chicken_consomme = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_chicken_consomme",
        limit_choices_to={"component_type__in": (Product.ComponentType.CHICKEN_CONSOMME, Product.ComponentType.VARIABLE_FIRST_COURSE)},
    )
    variable_first_course = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_variable_first_course",
        limit_choices_to={"component_type": Product.ComponentType.VARIABLE_FIRST_COURSE},
    )
    second_course_one = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_second_course_one",
        limit_choices_to={"component_type": Product.ComponentType.SECOND_COURSE},
    )
    second_course_two = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_second_course_two",
        limit_choices_to={"component_type": Product.ComponentType.SECOND_COURSE},
    )
    chicken_stew = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_chicken_stew",
        limit_choices_to={"component_type": Product.ComponentType.CHICKEN_STEW},
    )
    beef_stew = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_beef_stew",
        limit_choices_to={"component_type": Product.ComponentType.BEEF_STEW},
    )
    varied_stew = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_varied_stew",
        limit_choices_to={"component_type": Product.ComponentType.VARIED_STEW},
    )
    beans_order = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_beans_order",
        limit_choices_to={"component_type": Product.ComponentType.COMPLEMENT},
    )
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "menú diario"
        verbose_name_plural = "menús diarios"

    def __str__(self):
        return f"Menú {self.date:%d/%m/%Y} · {self.get_status_display()}"

    def clean(self):
        field_types = {
            "water_product": Product.ComponentType.DAILY_WATER,
            "variable_first_course": Product.ComponentType.VARIABLE_FIRST_COURSE,
            "second_course_one": Product.ComponentType.SECOND_COURSE,
            "second_course_two": Product.ComponentType.SECOND_COURSE,
            "chicken_stew": Product.ComponentType.CHICKEN_STEW,
            "beef_stew": Product.ComponentType.BEEF_STEW,
            "varied_stew": Product.ComponentType.VARIED_STEW,
            "beans_order": Product.ComponentType.COMPLEMENT,
        }
        errors = {}
        for field_name, expected_type in field_types.items():
            product = getattr(self, field_name)
            if product and product.component_type != expected_type:
                errors[field_name] = "El producto no corresponde al tipo requerido para este lugar."
        if self.chicken_consomme and self.chicken_consomme.component_type not in {
            Product.ComponentType.CHICKEN_CONSOMME,
            Product.ComponentType.VARIABLE_FIRST_COURSE,
        }:
            errors["chicken_consomme"] = "Selecciona un producto configurado como sopa."
        if self.chicken_consomme_id and self.chicken_consomme_id == self.variable_first_course_id:
            errors["variable_first_course"] = "Selecciona una sopa diferente."
        if self.second_course_one_id and self.second_course_one_id == self.second_course_two_id:
            errors["second_course_two"] = "Selecciona un segundo tiempo diferente."
        if errors:
            raise ValidationError(errors)

    @property
    def first_course_options(self):
        return (self.chicken_consomme, self.variable_first_course)

    @property
    def second_course_options(self):
        return (self.second_course_one, self.second_course_two)

    @property
    def stew_options(self):
        return (self.chicken_stew, self.beef_stew, self.varied_stew)


class MealPackage(models.Model):
    class PackageType(models.TextChoices):
        RUNNING = "running", "Comida corrida"
        EXECUTIVE = "executive", "Comida ejecutiva"

    package_type = models.CharField(max_length=20, choices=PackageType.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_without_water = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    price_with_water = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    table_refill_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "paquete de comida"
        verbose_name_plural = "paquetes de comida"

    def __str__(self):
        return self.name

    def clean(self):
        if (
            self.price_with_water is not None
            and self.price_without_water is not None
            and self.price_with_water < self.price_without_water
        ):
            raise ValidationError({
                "price_with_water": "El precio con agua no puede ser menor que el precio sin agua."
            })


class DailyProductStock(models.Model):
    class StockType(models.TextChoices):
        DAILY = "daily", "Menú diario"
        FIXED = "fixed", "Menú fijo"

    class ItemKind(models.TextChoices):
        PRODUCT = "product", "Producto"
        TORTILLAS = "tortillas", "Porción de tortillas"
        BREAD = "bread", "Bolillo"

    class Channel(models.TextChoices):
        TABLE = "table", "Mesas"
        ORDERS = "orders", "Pedidos"
        SHARED = "shared", "Todos los canales"

    class ChickenPiece(models.TextChoices):
        LEG = "leg", "Pierna"
        THIGH = "thigh", "Muslo"

    stock_type = models.CharField(
        max_length=10, choices=StockType.choices, default=StockType.DAILY, db_index=True,
    )
    date = models.DateField(default=timezone.localdate, null=True, blank=True, db_index=True)
    item_kind = models.CharField(
        max_length=20, choices=ItemKind.choices, default=ItemKind.PRODUCT,
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="daily_stocks",
        null=True, blank=True,
    )
    daily_menu = models.ForeignKey(
        DailyMenu, on_delete=models.PROTECT, null=True, blank=True,
        related_name="product_stocks",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    chicken_piece = models.CharField(
        max_length=20, choices=ChickenPiece.choices, blank=True,
        help_text="Solo se usa para separar pierna y muslo del guisado de pollo.",
    )
    initial_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=15)
    is_tracked = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("date", "item_kind", "product__name", "channel")
        constraints = [
            models.UniqueConstraint(
                fields=("date", "product", "channel", "chicken_piece"),
                condition=models.Q(item_kind="product", stock_type="daily"),
                name="unique_daily_product_stock_channel",
            ),
            models.UniqueConstraint(
                fields=("date", "item_kind", "channel"),
                condition=~models.Q(item_kind="product") & models.Q(stock_type="daily"),
                name="unique_daily_supply_stock_channel",
            ),
            models.UniqueConstraint(
                fields=("product",),
                condition=models.Q(item_kind="product", stock_type="fixed"),
                name="unique_fixed_product_stock",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(item_kind="product", product__isnull=False)
                    | (~models.Q(item_kind="product") & models.Q(product__isnull=True))
                ),
                name="daily_stock_product_matches_kind",
            ),
        ]
        verbose_name = "existencia diaria"
        verbose_name_plural = "existencias diarias"

    def __str__(self):
        if self.stock_type == self.StockType.FIXED:
            return f"Menú fijo · {self.item_name}"
        return f"{self.date:%d/%m/%Y} · {self.item_name} · {self.get_channel_display()}"

    @property
    def item_name(self):
        if self.product_id:
            suffix = f" · {self.get_chicken_piece_display()}" if self.chicken_piece else ""
            return f"{self.product.name}{suffix}"
        return self.get_item_kind_display()

    @property
    def movement_total(self):
        return self.movements.aggregate(total=models.Sum("quantity"))["total"] or 0

    @property
    def available_quantity(self):
        return self.initial_quantity + self.movement_total

    @property
    def is_low_stock(self):
        return self.available_quantity <= self.low_stock_threshold


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        RESERVATION = "reservation", "Apartado para ticket"
        RELEASE = "release", "Devolución al inventario"
        CONSUMPTION = "consumption", "Consumo confirmado"
        ADJUSTMENT = "adjustment", "Ajuste manual"
        TRANSFER_IN = "transfer_in", "Entrada por transferencia"
        TRANSFER_OUT = "transfer_out", "Salida por transferencia"

    stock = models.ForeignKey(
        DailyProductStock, on_delete=models.PROTECT, related_name="movements",
    )
    quantity = models.IntegerField(
        help_text="Usa cantidades negativas para salidas y positivas para devoluciones o entradas.",
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    reference_type = models.CharField(
        max_length=30, blank=True,
        help_text="Origen del movimiento, por ejemplo order o table_account.",
    )
    reference_id = models.PositiveBigIntegerField(null=True, blank=True)
    note = models.CharField(max_length=250, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0),
                name="stock_movement_quantity_nonzero",
            ),
        ]
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"

    def __str__(self):
        sign = "+" if self.quantity > 0 else ""
        return f"{self.stock} · {sign}{self.quantity} · {self.get_reason_display()}"
