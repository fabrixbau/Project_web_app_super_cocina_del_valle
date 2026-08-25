# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración agrega tres datos al pedido: repartidor responsable, quién hizo la
# asignación y cuándo ocurrió. Son opcionales para conservar pedidos anteriores. Borra la nota.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0004_order_attention_and_optional_payment"),
    ]

    operations = [
        migrations.AddField(model_name="order", name="delivery_assigned_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="order", name="delivery_assigned_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_assignments_made", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="order", name="delivery_person", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_delivery_orders", to=settings.AUTH_USER_MODEL)),
    ]
