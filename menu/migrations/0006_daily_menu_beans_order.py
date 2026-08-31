# NOTA TEMPORAL PARA APRENDIZAJE:
# Este campo opcional enlaza el producto cobrable "Orden de frijoles" con el menú del día.
# No se agrega automáticamente a menús anteriores y nunca forma parte de un paquete.
# Borra esta nota después de leerla.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0005_table_category_modes"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailymenu",
            name="beans_order",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"component_type": "complement"},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="daily_menus_as_beans_order",
                to="menu.product",
            ),
        ),
    ]
