from django.db import migrations, models
import django.db.models.deletion


def classify_existing_daily_waters(apps, schema_editor):
    DailyMenu = apps.get_model("menu", "DailyMenu")
    Product = apps.get_model("menu", "Product")
    water_ids = DailyMenu.objects.exclude(water_product_id=None).values_list(
        "water_product_id", flat=True,
    )
    Product.objects.filter(pk__in=water_ids).update(component_type="daily_water")


def restore_beverage_type(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    Product.objects.filter(component_type="daily_water").update(component_type="beverage")


class Migration(migrations.Migration):
    dependencies = [("menu", "0014_alter_dailymenu_chicken_consomme")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="component_type",
            field=models.CharField(
                choices=[
                    ("general", "Producto general"),
                    ("chicken_consomme", "Consomé de pollo"),
                    ("variable_first_course", "Primer tiempo variable"),
                    ("second_course", "Segundo tiempo (arroz o espagueti)"),
                    ("chicken_stew", "Guisado de pollo"),
                    ("beef_stew", "Guisado de res"),
                    ("varied_stew", "Guisado variado"),
                    ("grill", "Producto de plancha"),
                    ("beverage", "Bebida"),
                    ("daily_water", "Agua del menú diario"),
                    ("complement", "Complemento"),
                ],
                default="general",
                max_length=30,
            ),
        ),
        migrations.RunPython(classify_existing_daily_waters, restore_beverage_type),
        migrations.AlterField(
            model_name="dailymenu",
            name="water_product",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"component_type": "daily_water"},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="daily_menus_as_water",
                to="menu.product",
            ),
        ),
    ]
