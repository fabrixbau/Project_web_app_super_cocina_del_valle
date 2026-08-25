from django.db import migrations, models
import django.core.validators


def create_default_packages(apps, schema_editor):
    MealPackage = apps.get_model("menu", "MealPackage")
    defaults = (
        ("running", "Comida corrida", "Tres tiempos con guisado del menú diario.", 10),
        ("executive", "Comida ejecutiva", "Tres tiempos con producto de plancha elegible.", 20),
    )
    for package_type, name, description, sort_order in defaults:
        MealPackage.objects.get_or_create(package_type=package_type, defaults={
            "name": name, "description": description, "price_without_water": 0,
            "price_with_water": 0, "table_refill_price": 0, "sort_order": sort_order,
        })


def remove_default_packages(apps, schema_editor):
    MealPackage = apps.get_model("menu", "MealPackage")
    MealPackage.objects.filter(package_type__in=("running", "executive")).delete()


class Migration(migrations.Migration):
    dependencies = [("menu", "0003_fixed_daily_menu_structure")]
    operations = [
        migrations.CreateModel(
            name="MealPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_type", models.CharField(choices=[("running", "Comida corrida"), ("executive", "Comida ejecutiva")], max_length=20, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("price_without_water", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("price_with_water", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("table_refill_price", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "paquete de comida", "verbose_name_plural": "paquetes de comida", "ordering": ["sort_order", "name"]},
        ),
        migrations.RunPython(create_default_packages, remove_default_packages),
    ]
