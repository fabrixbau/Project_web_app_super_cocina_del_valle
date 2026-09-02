# NOTA TEMPORAL PARA APRENDIZAJE: Estos campos identifican al telefonista y la hora prometida al cliente sin cambiar pedidos anteriores. Borra esta nota después de aplicar la migración.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("orders", "0008_order_item_customization_comment"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name="order", name="created_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="internal_orders_created", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="order", name="requested_for", field=models.DateTimeField(blank=True, null=True, verbose_name="hora solicitada")),
    ]
