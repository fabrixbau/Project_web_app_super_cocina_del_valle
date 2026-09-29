from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0030_order_transferred_from_table_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="terminalmovement",
            name="classification_color",
            field=models.CharField(blank=True, max_length=32),
        ),
    ]
