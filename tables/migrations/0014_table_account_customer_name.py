# NOTA TEMPORAL PARA APRENDIZAJE:
# Agregamos un nombre opcional a cada cuenta. Las cuentas anteriores quedan con texto vacío y
# continúan apareciendo normalmente en el historial. Borra esta nota, pero conserva la migración.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tables", "0013_table_item_customization_comment")]
    operations = [
        migrations.AddField(
            model_name="tableaccount", name="customer_name",
            field=models.CharField(blank=True, max_length=100, verbose_name="nombre del cliente"),
        ),
    ]
