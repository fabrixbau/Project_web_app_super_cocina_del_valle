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

from django.core.validators import MinValueValidator
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
        COMPLEMENT = "complement", "Complemento"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu/products/", blank=True)
    is_available = models.BooleanField(default=True)
    component_type = models.CharField(
        max_length=30,
        choices=ComponentType.choices,
        default=ComponentType.GENERAL,
    )
    service_periods = models.ManyToManyField(ServicePeriod, blank=True, related_name="products")
    is_sold_individually = models.BooleanField(default=True)
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
        limit_choices_to={"component_type": Product.ComponentType.BEVERAGE},
    )
    chicken_consomme = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="daily_menus_as_chicken_consomme",
        limit_choices_to={"component_type": Product.ComponentType.CHICKEN_CONSOMME},
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
            "water_product": Product.ComponentType.BEVERAGE,
            "chicken_consomme": Product.ComponentType.CHICKEN_CONSOMME,
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
