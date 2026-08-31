# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta migración agrega una marca para distinguir una orden individual de un tiempo que
# está esperando completar comida corrida o ejecutiva. Los registros anteriores quedan
# como órdenes normales (`False`) para no alterar tickets históricos. Borra esta nota.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tables", "0009_table_item_daily_menu"),
    ]

    operations = [
        migrations.AddField(
            model_name="tableaccountitem",
            name="is_package_candidate",
            field=models.BooleanField(default=False),
        ),
    ]
