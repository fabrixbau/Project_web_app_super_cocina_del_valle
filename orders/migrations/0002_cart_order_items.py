# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración amplía OrderItem sin perder pedidos existentes. Las filas actuales se
# consideran paquetes; las nuevas también podrán representar productos individuales.
# Borra esta nota después de leerla.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("orders", "0001_initial")]
    operations = [
        migrations.AddField(model_name="orderitem", name="item_type", field=models.CharField(choices=[("package", "Paquete"), ("product", "Producto individual")], default="package", max_length=20)),
        migrations.AddField(model_name="orderitem", name="product_name_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="orderitem", name="product", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="individual_order_items", to="menu.product")),
        migrations.AlterField(model_name="orderitem", name="package", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="menu.mealpackage")),
        migrations.AlterField(model_name="orderitem", name="package_name_snapshot", field=models.CharField(blank=True, max_length=100)),
        migrations.AlterField(model_name="orderitem", name="first_course", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_first_course", to="menu.product")),
        migrations.AlterField(model_name="orderitem", name="first_course_name_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AlterField(model_name="orderitem", name="second_course", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_second_course", to="menu.product")),
        migrations.AlterField(model_name="orderitem", name="second_course_name_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AlterField(model_name="orderitem", name="main_course", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_main_course", to="menu.product")),
        migrations.AlterField(model_name="orderitem", name="main_course_name_snapshot", field=models.CharField(blank=True, max_length=150)),
    ]
