# NOTA TEMPORAL PARA APRENDIZAJE:
# Una sola posición general no alcanza para ordenar distinto desayuno y comida. Estos
# campos permiten configurar ambos modos desde Menú sin depender del nombre de categorías.
# La migración copia el orden actual como punto de partida. Borra esta nota al terminar.

from django.db import migrations, models


def copy_current_order(apps, schema_editor):
    Category = apps.get_model("menu", "Category")
    for category in Category.objects.all():
        Category.objects.filter(pk=category.pk).update(
            table_breakfast_order=category.sort_order,
            table_lunch_order=category.sort_order,
        )


class Migration(migrations.Migration):
    dependencies = [("menu", "0004_meal_packages")]
    operations = [
        migrations.AddField(model_name="category", name="table_breakfast_order", field=models.PositiveIntegerField(default=0, verbose_name="orden en desayunos")),
        migrations.AddField(model_name="category", name="table_lunch_order", field=models.PositiveIntegerField(default=0, verbose_name="orden en comida")),
        migrations.AddField(model_name="category", name="show_on_table_breakfast", field=models.BooleanField(default=True, verbose_name="mostrar en modo desayunos")),
        migrations.AddField(model_name="category", name="show_on_table_lunch", field=models.BooleanField(default=True, verbose_name="mostrar en modo comida")),
        migrations.AddField(model_name="category", name="show_table_packages", field=models.BooleanField(default=False, help_text="Actívalo en la categoría que debe abrir Comida corrida y ejecutiva.", verbose_name="mostrar paquetes de mesa al elegirla")),
        migrations.RunPython(copy_current_order, migrations.RunPython.noop),
    ]
