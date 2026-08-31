# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración agrega la clave que une alternativas equivalentes, sin modificar las opciones
# que ya existen. Después de aplicarla puedes borrar este comentario, no el archivo. 

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("menu", "0008_product_customization_groups")]

    operations = [
        migrations.AddField(
            model_name="productoption",
            name="replacement_pair",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
