# NOTA TEMPORAL PARA APRENDIZAJE:
# Las referencias opcionales permiten reabrir una comida y saber qué tiempos estaban
# elegidos. Las partidas anteriores se consideran completas para no bloquear cuentas viejas.
# Borra esta nota después de aplicar y comprender la migración.

from django.db import migrations, models
import django.db.models.deletion


def connect_existing_snapshots(apps, schema_editor):
    TableAccountItem = apps.get_model("tables", "TableAccountItem")
    Product = apps.get_model("menu", "Product")
    for item in TableAccountItem.objects.filter(item_type="package"):
        values = {}
        for snapshot_field, product_field in (
            ("first_course_snapshot", "first_course_product_id"),
            ("second_course_snapshot", "second_course_product_id"),
            ("main_course_snapshot", "main_course_product_id"),
        ):
            name = getattr(item, snapshot_field)
            if name:
                values[product_field] = Product.objects.filter(name=name).values_list("pk", flat=True).first()
        TableAccountItem.objects.filter(pk=item.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0005_table_category_modes"),
        ("tables", "0007_horizontal_table_map"),
    ]
    operations = [
        migrations.AddField(model_name="tableaccountitem", name="first_course_product", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_items_as_first_course", to="menu.product")),
        migrations.AddField(model_name="tableaccountitem", name="second_course_product", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_items_as_second_course", to="menu.product")),
        migrations.AddField(model_name="tableaccountitem", name="main_course_product", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_items_as_main_course", to="menu.product")),
        migrations.AddField(model_name="tableaccountitem", name="is_complete", field=models.BooleanField(default=True)),
        migrations.RunPython(connect_existing_snapshots, migrations.RunPython.noop),
    ]
