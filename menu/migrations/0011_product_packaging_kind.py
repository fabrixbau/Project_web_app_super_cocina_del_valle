from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("menu", "0010_shared_ingredient_groups")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="packaging_kind",
            field=models.CharField(
                choices=[
                    ("none", "No es envase"),
                    ("package", "Paquete de envases"),
                    ("individual", "Envase individual"),
                    ("customer_own", "Cliente trae recipientes"),
                ],
                db_index=True,
                default="none",
                help_text="Los envases aparecen en una barra rápida exclusiva para Mesas y Pedidos.",
                max_length=20,
                verbose_name="tipo de envase",
            ),
        ),
    ]
