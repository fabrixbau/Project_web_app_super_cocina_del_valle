# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración agrega a la cuenta cerrada la fotografía del pago y sus responsables.
# Los campos permiten nulos para conservar intactas cuentas creadas antes de este bloque.
# Borra esta nota después de leerla.

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tables", "0005_table_package_items"),
    ]
    operations = [
        migrations.AddField(model_name="tableaccount", name="closed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="closed_table_accounts", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="tableaccount", name="payment_method", field=models.CharField(blank=True, choices=[("cash", "Efectivo"), ("card", "Tarjeta"), ("transfer", "Transferencia")], max_length=20)),
        migrations.AddField(model_name="tableaccount", name="subtotal_closed", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="tableaccount", name="tip_amount", field=models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[MinValueValidator(0)])),
        migrations.AddField(model_name="tableaccount", name="tip_recipient", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="table_tips_received", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="tableaccount", name="total_paid", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="tableaccount", name="cash_tendered", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="tableaccount", name="change_given", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
    ]
