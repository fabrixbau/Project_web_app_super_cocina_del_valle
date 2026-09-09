# NOTA TEMPORAL PARA APRENDIZAJE: estos campos guardan cuándo y quién terminó la
# revisión de Caja sin modificar el estado operativo del pedido. Borra esta nota.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0015_order_cash_handoff"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AddField(model_name="order", name="cashier_released_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="order", name="cashier_released_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cashier_orders_released", to=settings.AUTH_USER_MODEL),
        ),
    ]
