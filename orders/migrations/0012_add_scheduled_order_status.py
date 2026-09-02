from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0011_orderitem_is_package_candidate")]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Capturando"),
                    ("pending_confirmation", "Pendiente de confirmar"),
                    ("confirmed", "Confirmado"),
                    ("scheduled", "Programado"),
                    ("preparing", "En preparación"),
                    ("ready", "Listo"),
                    ("out_for_delivery", "En reparto"),
                    ("picked_up", "Recogido"),
                    ("delivered", "Entregado"),
                    ("canceled", "Cancelado"),
                ],
                default="pending_confirmation",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="orderstatushistory",
            name="to_status",
            field=models.CharField(
                choices=[
                    ("draft", "Capturando"),
                    ("pending_confirmation", "Pendiente de confirmar"),
                    ("confirmed", "Confirmado"),
                    ("scheduled", "Programado"),
                    ("preparing", "En preparación"),
                    ("ready", "Listo"),
                    ("out_for_delivery", "En reparto"),
                    ("picked_up", "Recogido"),
                    ("delivered", "Entregado"),
                    ("canceled", "Cancelado"),
                ],
                max_length=30,
            ),
        ),
    ]
