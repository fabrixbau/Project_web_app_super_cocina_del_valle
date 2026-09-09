# NOTA TEMPORAL PARA APRENDIZAJE: estas restricciones garantizan también en base de
# datos que un pedido o mesa no se concilie dos veces. Borra esta nota al leerla.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0018_terminal_cut_and_movements")]

    operations = [
        migrations.AddConstraint(
            model_name="terminalmovement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("order__isnull", False)), fields=("order",),
                name="unique_terminal_movement_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="terminalmovement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("table_account__isnull", False)), fields=("table_account",),
                name="unique_terminal_movement_table",
            ),
        ),
    ]
