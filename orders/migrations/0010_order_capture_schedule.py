# NOTA TEMPORAL PARA APRENDIZAJE: Separamos fecha y hora porque una entrega conoce el día aunque todavía no tenga hora; también agregamos el estado de captura. Borra esta nota al aplicar.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0009_order_internal_capture_fields")]
    operations = [
        migrations.AddField(model_name="order", name="requested_date", field=models.DateField(blank=True, null=True, verbose_name="fecha solicitada")),
        migrations.AddField(model_name="order", name="requested_time", field=models.TimeField(blank=True, null=True, verbose_name="hora solicitada")),
        migrations.AlterField(model_name="order", name="status", field=models.CharField(choices=[("draft", "Capturando"), ("pending_confirmation", "Pendiente de confirmar"), ("confirmed", "Confirmado"), ("preparing", "En preparación"), ("ready", "Listo"), ("out_for_delivery", "En reparto"), ("picked_up", "Recogido"), ("delivered", "Entregado"), ("canceled", "Cancelado")], default="pending_confirmation", max_length=30)),
        migrations.AlterField(model_name="orderstatushistory", name="to_status", field=models.CharField(choices=[("draft", "Capturando"), ("pending_confirmation", "Pendiente de confirmar"), ("confirmed", "Confirmado"), ("preparing", "En preparación"), ("ready", "Listo"), ("out_for_delivery", "En reparto"), ("picked_up", "Recogido"), ("delivered", "Entregado"), ("canceled", "Cancelado")], max_length=30)),
    ]
