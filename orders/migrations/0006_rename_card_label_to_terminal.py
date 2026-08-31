# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración solo actualiza el nombre visible del método; los registros siguen guardando
# `card`, por lo que ningún pedido anterior cambia ni se pierde. Borra esta nota al leerla.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0005_order_delivery_assignment")]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cash", "Efectivo"),
                    ("card", "Terminal"),
                    ("transfer", "Transferencia"),
                ],
                max_length=20,
            ),
        ),
    ]
