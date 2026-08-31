# NOTA TEMPORAL PARA APRENDIZAJE:
# El comentario se guarda en la partida para conservar instrucciones como "dorada la salchicha"
# aunque después cambie el producto. Puedes borrar la nota, pero conserva la migración.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0007_order_item_customization")]
    operations = [
        migrations.AddField(
            model_name="orderitem", name="customization_comment",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
