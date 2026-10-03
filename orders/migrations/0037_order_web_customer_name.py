from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0036_seed_delivery_streets"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="web_customer_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="nombre con el que pidió"),
        ),
    ]
