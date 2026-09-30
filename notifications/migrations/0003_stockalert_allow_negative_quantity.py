from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0002_stockalert_stockalertdismissal")]

    operations = [
        migrations.AlterField(
            model_name="stockalert",
            name="available_quantity",
            field=models.IntegerField(),
        ),
    ]
