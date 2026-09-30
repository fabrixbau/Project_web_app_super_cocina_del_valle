from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("menu", "0022_product_uses_bread_stock"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="InventoryAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prepared_before", models.IntegerField()),
                ("prepared_after", models.IntegerField()),
                ("threshold_before", models.PositiveIntegerField()),
                ("threshold_after", models.PositiveIntegerField()),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("stock", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="audit_logs", to="menu.dailyproductstock")),
            ],
            options={"verbose_name": "auditoría de existencia", "verbose_name_plural": "auditoría de existencias", "ordering": ("-created_at", "-pk")},
        ),
    ]
