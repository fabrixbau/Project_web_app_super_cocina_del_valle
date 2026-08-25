# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración crea las alertas relacionadas con pedidos y el registro del empleado que
# las marca como atendidas. Borra esta nota después de leerla.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0002_cart_order_items"),
    ]
    operations = [
        migrations.CreateModel(
            name="InternalNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notification_type", models.CharField(choices=[("new_public_order", "Nuevo pedido web")], max_length=40)),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="orders.order")),
                ("read_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="read_internal_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["is_read", "-created_at"]},
        ),
    ]
