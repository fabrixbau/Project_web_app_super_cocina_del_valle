# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración solo cambia las coordenadas visuales de las nueve mesas. No modifica
# cuentas ni tickets existentes. La fila superior contiene M8–M5 y M9; abajo M1–M4.
# Borra esta nota después de aplicar y comprender la migración.

from django.db import migrations


TABLE_LAYOUT = (
    ("Mesa 8", 1, 1, 1),
    ("Mesa 7", 1, 2, 2),
    ("Mesa 6", 1, 3, 3),
    ("Mesa 5", 1, 4, 4),
    ("Mesa 9", 1, 5, 5),
    ("Mesa 1", 2, 1, 6),
    ("Mesa 2", 2, 2, 7),
    ("Mesa 3", 2, 3, 8),
    ("Mesa 4", 2, 4, 9),
)


def arrange_horizontal_map(apps, schema_editor):
    DiningTable = apps.get_model("tables", "DiningTable")
    for name, row, column, order in TABLE_LAYOUT:
        DiningTable.objects.filter(name=name).update(
            map_row=row, map_column=column, display_order=order, is_active=True,
        )


class Migration(migrations.Migration):
    dependencies = [("tables", "0006_table_account_payment")]
    operations = [migrations.RunPython(arrange_horizontal_map, migrations.RunPython.noop)]
