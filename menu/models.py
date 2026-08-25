from django.core.exceptions import ValidationError
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

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self):
        return self.name


class Product(models.Model):
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
