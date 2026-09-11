from django.db import migrations, models


def set_daily_default_threshold(apps, schema_editor):
    Stock = apps.get_model("menu", "DailyProductStock")
    Stock.objects.filter(stock_type="daily", low_stock_threshold=10).update(
        low_stock_threshold=15,
    )


class Migration(migrations.Migration):
    dependencies = [("menu", "0020_remove_dailyproductstock_unique_daily_supply_stock_channel_and_more")]

    operations = [
        migrations.AlterField(
            model_name="dailyproductstock",
            name="low_stock_threshold",
            field=models.PositiveIntegerField(default=15),
        ),
        migrations.RunPython(set_daily_default_threshold, migrations.RunPython.noop),
    ]
