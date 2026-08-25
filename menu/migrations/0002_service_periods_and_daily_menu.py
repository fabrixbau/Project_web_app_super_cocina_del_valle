import datetime

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def create_default_periods(apps, schema_editor):
    ServicePeriod = apps.get_model("menu", "ServicePeriod")
    ServicePeriod.objects.update_or_create(
        code="breakfast",
        defaults={"name": "Desayuno", "start_time": datetime.time(8, 0), "end_time": datetime.time(13, 0), "sort_order": 10},
    )
    ServicePeriod.objects.update_or_create(
        code="lunch",
        defaults={"name": "Comida", "start_time": datetime.time(12, 30), "end_time": datetime.time(17, 0), "sort_order": 20},
    )


def remove_default_periods(apps, schema_editor):
    ServicePeriod = apps.get_model("menu", "ServicePeriod")
    ServicePeriod.objects.filter(code__in=("breakfast", "lunch")).delete()


class Migration(migrations.Migration):
    dependencies = [("menu", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="ServicePeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True)),
                ("name", models.CharField(max_length=80, unique=True)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
            ],
            options={"verbose_name": "periodo de servicio", "verbose_name_plural": "periodos de servicio", "ordering": ["sort_order", "start_time"]},
        ),
        migrations.AddField(
            model_name="product",
            name="component_type",
            field=models.CharField(choices=[("general", "Producto general"), ("first_course", "Primer tiempo (sopa, consomé o crema)"), ("second_course", "Segundo tiempo (arroz o espagueti)"), ("stew", "Guisado"), ("grill", "Producto de plancha"), ("beverage", "Bebida"), ("complement", "Complemento")], default="general", max_length=30),
        ),
        migrations.AddField(
            model_name="product",
            name="eligible_for_executive_meal",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="is_sold_individually",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="product",
            name="service_periods",
            field=models.ManyToManyField(blank=True, related_name="products", to="menu.serviceperiod"),
        ),
        migrations.CreateModel(
            name="DailyMenu",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(default=django.utils.timezone.localdate, unique=True)),
                ("status", models.CharField(choices=[("draft", "Borrador"), ("published", "Publicado"), ("closed", "Cerrado")], default="draft", max_length=20)),
                ("published_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("water_product", models.ForeignKey(blank=True, limit_choices_to={"component_type": "beverage"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_water", to="menu.product")),
            ],
            options={"verbose_name": "menú diario", "verbose_name_plural": "menús diarios", "ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="DailyMenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_available", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("daily_menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="menu.dailymenu")),
                ("product", models.ForeignKey(limit_choices_to={"component_type__in": ("first_course", "second_course", "stew")}, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menu_items", to="menu.product")),
            ],
            options={
                "verbose_name": "elemento del menú diario",
                "verbose_name_plural": "elementos del menú diario",
                "ordering": ["product__component_type", "sort_order", "product__name"],
                "constraints": [models.UniqueConstraint(fields=("daily_menu", "product"), name="unique_product_per_daily_menu")],
            },
        ),
        migrations.RunPython(create_default_periods, remove_default_periods),
    ]
