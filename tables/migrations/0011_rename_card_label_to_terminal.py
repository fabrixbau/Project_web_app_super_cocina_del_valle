# NOTA TEMPORAL PARA APRENDIZAJE:
# La cuenta de mesa conserva `card` como valor interno y cambia solamente su etiqueta visible
# a Terminal. Esto mantiene compatibles los cobros ya registrados. Borra esta nota al leerla.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tables", "0010_table_item_package_candidate")]

    operations = [
        migrations.AlterField(
            model_name="tableaccount",
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
