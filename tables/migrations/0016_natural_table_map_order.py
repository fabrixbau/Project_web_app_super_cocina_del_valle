from django.db import migrations


NATURAL_LAYOUT = (
    ("Mesa 1", 1, 1, 1),
    ("Mesa 2", 1, 2, 2),
    ("Mesa 3", 1, 3, 3),
    ("Mesa 4", 1, 4, 4),
    ("Mesa 5", 1, 5, 5),
    ("Mesa 6", 2, 1, 6),
    ("Mesa 7", 2, 2, 7),
    ("Mesa 8", 2, 3, 8),
    ("Mesa 9", 2, 4, 9),
)

PREVIOUS_LAYOUT = (
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


def _apply_layout(apps, layout):
    DiningTable = apps.get_model("tables", "DiningTable")
    for name, row, column, order in layout:
        DiningTable.objects.filter(name=name).update(
            map_row=row,
            map_column=column,
            display_order=order,
            is_active=True,
        )


def arrange_naturally(apps, schema_editor):
    _apply_layout(apps, NATURAL_LAYOUT)


def restore_previous_layout(apps, schema_editor):
    _apply_layout(apps, PREVIOUS_LAYOUT)

PREVIOUS_LAYOUT = (
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


def apply_layout(apps, layout):
    DiningTable = apps.get_model("tables", "DiningTable")
    for name, row, column, display_order in layout:
        DiningTable.objects.filter(name=name).update(
            map_row=row,
            map_column=column,
            display_order=display_order,
            is_active=True,
        )


def arrange_naturally(apps, schema_editor):
    apply_layout(apps, NATURAL_LAYOUT)


def restore_previous_layout(apps, schema_editor):
    apply_layout(apps, PREVIOUS_LAYOUT)


class Migration(migrations.Migration):
    dependencies = [("tables", "0015_tableactivity")]
    operations = [migrations.RunPython(arrange_naturally, restore_previous_layout)]
