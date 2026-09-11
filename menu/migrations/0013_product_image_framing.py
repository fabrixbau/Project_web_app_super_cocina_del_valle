from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("menu", "0012_create_packaging_catalog")]
    operations = [
        migrations.AddField(model_name="product", name="image_position_x", field=models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])),
        migrations.AddField(model_name="product", name="image_position_y", field=models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)])),
        migrations.AddField(model_name="product", name="image_zoom", field=models.DecimalField(decimal_places=2, default=1, max_digits=3, validators=[MinValueValidator(1), MaxValueValidator(3)])),
    ]
