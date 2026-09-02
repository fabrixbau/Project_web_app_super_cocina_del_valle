# NOTA TEMPORAL PARA APRENDIZAJE: esta migración agrega la constancia de que Caja
# entregó el cambio. Los pedidos existentes comienzan como no confirmados para evitar
# afirmar un movimiento de efectivo que nunca registramos. Borra esta nota al leerla.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0014_customer_agenda"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AddField(model_name="order", name="cash_handoff_confirmed", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="order", name="cash_handoff_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="order", name="cash_handoff_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cash_handoffs_confirmed", to=settings.AUTH_USER_MODEL),
        ),
    ]
