# NOTA TEMPORAL PARA APRENDIZAJE:
# Agregamos coordenadas simples y sembramos las nueve mesas reales. `update_or_create`
# conserva Mesa 1 y Mesa 2 si ya las probaste, y completa el resto sin duplicarlas.
# Borra esta nota después de aplicar y comprender la migración.

from django.db import migrations, models


TABLE_LAYOUT = (
    ("Mesa 1", 1, 1, 1),
    ("Mesa 8", 1, 3, 8),
    ("Mesa 2", 2, 1, 2),
    ("Mesa 7", 2, 3, 7),
    ("Mesa 3", 3, 1, 3),
    ("Mesa 6", 3, 3, 6),
    ("Mesa 4", 4, 1, 4),
    ("Mesa 5", 4, 3, 5),
    ("Mesa 9", 5, 2, 9),
)


def create_fixed_table_map(apps, schema_editor):
    DiningTable = apps.get_model("tables", "DiningTable")
    for name, row, column, order in TABLE_LAYOUT:
        DiningTable.objects.update_or_create(
            name=name,
            defaults={
                "map_row": row,
                "map_column": column,
                "display_order": order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("tables", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="diningtable",
            name="map_column",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="columna en mapa"),
        ),
        migrations.AddField(
            model_name="diningtable",
            name="map_row",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="fila en mapa"),
        ),
        migrations.RunPython(create_fixed_table_map, migrations.RunPython.noop),
    ]
