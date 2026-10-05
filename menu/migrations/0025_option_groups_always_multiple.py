from django.db import migrations


def make_all_groups_multiple(apps, schema_editor):
    # Ingredientes y personalización: ya no existe "Elegir una opción"; los grupos que la
    # tenían pasan a "Elegir varias opciones".
    ProductOptionGroup = apps.get_model("menu", "ProductOptionGroup")
    ProductOptionGroup.objects.exclude(selection_type="multiple").update(selection_type="multiple")


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0024_product_show_to_customers"),
    ]

    operations = [
        migrations.RunPython(make_all_groups_multiple, migrations.RunPython.noop),
    ]
