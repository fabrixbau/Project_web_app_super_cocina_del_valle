# NOTA TEMPORAL PARA APRENDIZAJE:
# Cada paquete necesita recordar el menú diario que le dio sus opciones. Intentamos enlazar
# partidas existentes por la fecha en que se agregaron, para recuperar tickets de ayer.
# Borra esta nota después de aplicar y comprender la migración.

from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion


def connect_existing_items_to_daily_menu(apps, schema_editor):
    DailyMenu = apps.get_model("menu", "DailyMenu")
    TableAccountItem = apps.get_model("tables", "TableAccountItem")
    menus_by_date = {menu.date: menu.pk for menu in DailyMenu.objects.all()}
    for item in TableAccountItem.objects.filter(item_type="package", daily_menu__isnull=True):
        menu_id = menus_by_date.get(timezone.localtime(item.added_at).date())
        if menu_id:
            TableAccountItem.objects.filter(pk=item.pk).update(daily_menu_id=menu_id)


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0005_table_category_modes"),
        ("tables", "0008_progressive_table_packages"),
    ]
    operations = [
        migrations.AddField(
            model_name="tableaccountitem",
            name="daily_menu",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="table_account_items", to="menu.dailymenu",
            ),
        ),
        migrations.RunPython(connect_existing_items_to_daily_menu, migrations.RunPython.noop),
    ]
