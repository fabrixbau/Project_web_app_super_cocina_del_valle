# NOTA TEMPORAL PARA APRENDIZAJE: renombramos los campos existentes en vez de borrar
# y crear otros. Así cualquier confirmación previa conserva sus datos y ahora expresa
# correctamente la conciliación al final del día. Borra esta nota al leerla.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0016_order_cashier_release")]

    operations = [
        migrations.RenameField(model_name="order", old_name="cash_handoff_confirmed", new_name="cash_settlement_confirmed"),
        migrations.RenameField(model_name="order", old_name="cash_handoff_by", new_name="cash_settlement_by"),
        migrations.RenameField(model_name="order", old_name="cash_handoff_at", new_name="cash_settlement_at"),
        migrations.AlterField(
            model_name="order", name="cash_settlement_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cash_settlements_confirmed", to=settings.AUTH_USER_MODEL),
        ),
    ]
