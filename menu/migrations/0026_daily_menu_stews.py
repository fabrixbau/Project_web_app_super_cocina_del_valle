import django.db.models.deletion
from django.db import migrations, models


def copy_fixed_stews(apps, schema_editor):
    DailyMenu = apps.get_model("menu", "DailyMenu")
    DailyMenuStew = apps.get_model("menu", "DailyMenuStew")
    rows = []
    for menu in DailyMenu.objects.all():
        position = 0
        seen = set()
        for product_id in (menu.chicken_stew_id, menu.beef_stew_id, menu.varied_stew_id):
            if product_id and product_id not in seen:
                seen.add(product_id)
                position += 1
                rows.append(DailyMenuStew(daily_menu_id=menu.pk, product_id=product_id, sort_order=position))
    DailyMenuStew.objects.bulk_create(rows)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0025_option_groups_always_multiple"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyMenuStew",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.PositiveSmallIntegerField(default=1)),
                ("daily_menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="stew_entries", to="menu.dailymenu")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="daily_menu_stew_entries", to="menu.product")),
            ],
            options={
                "verbose_name": "guisado del menú diario",
                "verbose_name_plural": "guisados del menú diario",
                "ordering": ("sort_order", "id"),
                "constraints": [models.UniqueConstraint(fields=("daily_menu", "product"), name="unique_daily_menu_stew")],
            },
        ),
        migrations.RunPython(copy_fixed_stews, migrations.RunPython.noop),
    ]
