# NOTA TEMPORAL PARA APRENDIZAJE:
# El cliente necesita órdenes y visibilidades diferentes para desayuno y comida. Copiamos
# el orden general como inicio y dejamos todas visibles para no ocultar el menú existente.
# Borra esta nota después de leerla.

from django.db import migrations, models


def copy_general_order(apps, schema_editor):
    Category = apps.get_model("menu", "Category")
    for category in Category.objects.all():
        Category.objects.filter(pk=category.pk).update(
            public_breakfast_order=category.sort_order,
            public_lunch_order=category.sort_order,
        )


class Migration(migrations.Migration):
    dependencies = [("menu", "0006_daily_menu_beans_order")]
    operations = [
        migrations.AddField(model_name="category", name="public_breakfast_order", field=models.PositiveIntegerField(default=0, verbose_name="orden público en desayunos")),
        migrations.AddField(model_name="category", name="public_lunch_order", field=models.PositiveIntegerField(default=0, verbose_name="orden público en comida")),
        migrations.AddField(model_name="category", name="show_on_public_breakfast", field=models.BooleanField(default=True, verbose_name="mostrar al cliente en desayunos")),
        migrations.AddField(model_name="category", name="show_on_public_lunch", field=models.BooleanField(default=True, verbose_name="mostrar al cliente en comida")),
        migrations.RunPython(copy_general_order, migrations.RunPython.noop),
    ]
