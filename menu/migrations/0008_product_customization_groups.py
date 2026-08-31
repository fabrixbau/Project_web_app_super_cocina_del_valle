# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración crea grupos de preparación por producto y sus ingredientes/opciones.
# `is_default` distingue la receta estándar y `price_adjustment` permite cargos adicionales.
# Borra esta nota después de aplicar y comprender la migración.

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("menu", "0007_public_category_modes")]

    operations = [
        migrations.CreateModel(
            name="ProductOptionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("selection_type", models.CharField(choices=[("single", "Elegir una opción"), ("multiple", "Elegir varias opciones")], default="multiple", max_length=20)),
                ("is_required", models.BooleanField(default=False)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="option_groups", to="menu.product")),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.CreateModel(
            name="ProductOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("price_adjustment", models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("is_default", models.BooleanField(default=False)),
                ("is_available", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="menu.productoptiongroup")),
            ],
            options={"ordering": ("sort_order", "id")},
        ),
        migrations.AddConstraint(
            model_name="productoptiongroup",
            constraint=models.UniqueConstraint(fields=("product", "name"), name="unique_product_option_group_name"),
        ),
        migrations.AddConstraint(
            model_name="productoption",
            constraint=models.UniqueConstraint(fields=("group", "name"), name="unique_product_option_name"),
        ),
    ]
