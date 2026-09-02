import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0012_add_scheduled_order_status")]

    operations = [
        migrations.AddField(
            model_name="order", name="delivery_tip_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="order", name="delivery_tip_recipient",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_tips_received", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="order", name="delivery_tip_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order", name="delivery_tip_updated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="delivery_tips_updated", to=settings.AUTH_USER_MODEL),
        ),
    ]
