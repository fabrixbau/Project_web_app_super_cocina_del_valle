# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración permite pago vacío para recoger y agrega quién/cuándo inició la atención.
# Los pedidos anteriores conservan todos sus datos. Borra esta nota después de leerla.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0003_order_status_history"),
    ]
    operations = [
        migrations.AlterField(
            model_name="order", name="payment_method",
            field=models.CharField(blank=True, choices=[("cash", "Efectivo"), ("card", "Tarjeta"), ("transfer", "Transferencia")], max_length=20),
        ),
        migrations.AddField(
            model_name="order", name="attention_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order", name="attention_started_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders_attention_started", to=settings.AUTH_USER_MODEL),
        ),
    ]
