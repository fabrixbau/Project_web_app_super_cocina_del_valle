import unicodedata

from django.db import migrations, models
import django.db.models.deletion


def normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(character for character in normalized if not unicodedata.combining(character)).casefold()


def classify_existing_products(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    for product in Product.objects.filter(component_type="first_course"):
        product.component_type = "chicken_consomme" if "consom" in normalize_text(product.name) else "variable_first_course"
        product.save(update_fields=["component_type"])
    Product.objects.filter(component_type="stew").update(component_type="varied_stew")


def restore_old_classifications(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    Product.objects.filter(component_type__in=("chicken_consomme", "variable_first_course")).update(component_type="first_course")
    Product.objects.filter(component_type__in=("chicken_stew", "beef_stew", "varied_stew")).update(component_type="stew")


class Migration(migrations.Migration):
    dependencies = [("menu", "0002_service_periods_and_daily_menu")]
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
                    ("complement", "Complemento"),
                ],
                default="general",
                max_length=30,
            ),
        ),
        migrations.RunPython(classify_existing_products, restore_old_classifications),
        migrations.AddField(
            model_name="dailymenu",
            name="chicken_consomme",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "chicken_consomme"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_chicken_consomme", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="variable_first_course",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "variable_first_course"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_variable_first_course", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="second_course_one",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "second_course"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_second_course_one", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="second_course_two",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "second_course"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_second_course_two", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="chicken_stew",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "chicken_stew"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_chicken_stew", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="beef_stew",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "beef_stew"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_beef_stew", to="menu.product"),
        ),
        migrations.AddField(
            model_name="dailymenu",
            name="varied_stew",
            field=models.ForeignKey(blank=True, limit_choices_to={"component_type": "varied_stew"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_menus_as_varied_stew", to="menu.product"),
        ),
        migrations.DeleteModel(name="DailyMenuItem"),
    ]
