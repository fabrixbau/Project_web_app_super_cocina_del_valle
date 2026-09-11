from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0021_customer_debts")]
    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="bread",
            field=models.BooleanField(default=False),
        ),
    ]
