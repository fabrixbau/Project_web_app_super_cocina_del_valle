from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0019_unique_terminal_links")]

    operations = [
        migrations.AlterField(
            model_name="terminalcut",
            name="provider",
            field=models.CharField(
                choices=[
                    ("clover", "Clover"),
                    ("mercado_pago", "Mercado Pago"),
                    ("transfer", "Transferencias"),
                ],
                max_length=30,
            ),
        ),
    ]
