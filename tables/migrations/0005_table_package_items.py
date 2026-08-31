# NOTA TEMPORAL PARA APRENDIZAJE:
# Ampliamos una línea del ticket para fotografiar la configuración completa de un paquete
# de mesa. Los valores por defecto conservan los productos existentes. Borra esta nota.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("menu", "0004_meal_packages"), ("tables", "0004_table_commands")]
    operations = [
        migrations.AddField(model_name="tableaccountitem", name="item_type", field=models.CharField(choices=[("product", "Producto"), ("package", "Paquete")], default="product", max_length=20)),
        migrations.AddField(model_name="tableaccountitem", name="package", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_account_items", to="menu.mealpackage")),
        migrations.AddField(model_name="tableaccountitem", name="package_name_snapshot", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="tableaccountitem", name="first_course_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="tableaccountitem", name="second_course_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="tableaccountitem", name="main_course_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="tableaccountitem", name="chicken_piece", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="tableaccountitem", name="with_water", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="tableaccountitem", name="water_name_snapshot", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="tableaccountitem", name="tortillas", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="tableaccountitem", name="beans", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="tableaccountitem", name="refill_extra", field=models.BooleanField(default=False)),
    ]
