# NOTA TEMPORAL PARA APRENDIZAJE:
# Cada consumo conserva nombre y precio del momento aunque después cambie el menú. También
# registra quién y cuándo lo agregó para reconocer las rondas del servicio. Borra esta nota.

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("menu", "0004_meal_packages"),
        ("tables", "0002_fixed_nine_table_map"),
    ]
    operations = [
        migrations.CreateModel(
            name="TableAccountItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name_snapshot", models.CharField(max_length=150)),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("quantity", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="tables.tableaccount")),
                ("added_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="table_items_added", to=settings.AUTH_USER_MODEL)),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="table_account_items", to="menu.product")),
            ],
            options={"verbose_name": "consumo de mesa", "verbose_name_plural": "consumos de mesa", "ordering": ("added_at", "id")},
        ),
    ]
