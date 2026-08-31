# NOTA TEMPORAL PARA APRENDIZAJE:
# Mesas conserva el comentario en cada partida personalizada para mostrarlo junto al nombre del
# producto y mantenerlo en el historial. Borra esta nota después de leerla, no la migración.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tables", "0012_table_item_customization")]
    operations = [
        migrations.AddField(
            model_name="tableaccountitem", name="customization_comment",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
