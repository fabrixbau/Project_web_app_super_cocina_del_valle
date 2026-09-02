# NOTA TEMPORAL PARA APRENDIZAJE: Este indicador separa una orden individual de un tiempo
# que está esperando completar una comida corrida o ejecutiva. Borra esta nota al leerla.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0010_order_capture_schedule")]
    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="is_package_candidate",
            field=models.BooleanField(default=False),
        ),
    ]
