# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración añade el estado Recogido y la bitácora de transiciones. No inventa
# historial para pedidos anteriores; comenzarán a registrar desde su próximo cambio.
# Borra esta nota después de leerla.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0002_cart_order_items"),
    ]
    operations = [
        migrations.AlterField(
            model_name="order", name="status",
            field=models.CharField(choices=[
                ("pending_confirmation", "Pendiente de confirmar"), ("confirmed", "Confirmado"),
                ("preparing", "En preparación"), ("ready", "Listo"),
                ("out_for_delivery", "En reparto"), ("picked_up", "Recogido"),
                ("delivered", "Entregado"), ("canceled", "Cancelado"),
            ], default="pending_confirmation", max_length=30),
        ),
        migrations.CreateModel(
            name="OrderStatusHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("from_status", models.CharField(blank=True, max_length=30)),
                ("to_status", models.CharField(choices=[
                    ("pending_confirmation", "Pendiente de confirmar"), ("confirmed", "Confirmado"),
                    ("preparing", "En preparación"), ("ready", "Listo"),
                    ("out_for_delivery", "En reparto"), ("picked_up", "Recogido"),
                    ("delivered", "Entregado"), ("canceled", "Cancelado"),
                ], max_length=30)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_status_changes", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_history", to="orders.order")),
            ],
            options={"ordering": ["changed_at"]},
        ),
    ]
