# NOTA TEMPORAL PARA APRENDIZAJE:
# Estos campos fotografían la personalización de productos individuales en pedidos públicos.
# Los registros anteriores quedan como preparación estándar vacía. Borra esta nota.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0006_rename_card_label_to_terminal")]

    operations = [
        migrations.AddField(model_name="orderitem", name="configuration_snapshot", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="orderitem", name="configuration_signature", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="orderitem", name="is_customized", field=models.BooleanField(default=False)),
    ]
