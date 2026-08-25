# NOTA TEMPORAL PARA APRENDIZAJE:
# Crea `menu_category` y `menu_product`. Una migración aplicada no se reescribe;
# cambios futuros generan otra migración. Borra esta nota al terminar.

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("image", models.ImageField(blank=True, upload_to="menu/categories/")),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"verbose_name": "categoría", "verbose_name_plural": "categorías", "ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("description", models.TextField(blank=True)),
                ("image", models.ImageField(blank=True, upload_to="menu/products/")),
                ("is_available", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="menu.category")),
            ],
            options={
                "verbose_name": "producto", "verbose_name_plural": "productos",
                "ordering": ["category__sort_order", "category__name", "sort_order", "name"],
                "constraints": [models.UniqueConstraint(fields=("category", "name"), name="unique_product_name_per_category")],
            },
        ),
    ]
