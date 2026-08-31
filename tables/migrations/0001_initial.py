# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta primera migración crea las mesas físicas y sus cuentas. La restricción parcial en
# PostgreSQL garantiza una sola cuenta abierta por mesa incluso con dos usuarios. Borra la nota.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="DiningTable",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True, verbose_name="nombre")),
                ("display_order", models.PositiveIntegerField(default=0, verbose_name="orden visual")),
                ("is_active", models.BooleanField(default=True, verbose_name="activa")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "mesa", "verbose_name_plural": "mesas", "ordering": ("display_order", "name")},
        ),
        migrations.CreateModel(
            name="TableAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Abierta"), ("closed", "Cerrada")], default="open", max_length=10)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_waiter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="assigned_table_accounts", to=settings.AUTH_USER_MODEL)),
                ("opened_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="opened_table_accounts", to=settings.AUTH_USER_MODEL)),
                ("table", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="accounts", to="tables.diningtable")),
            ],
            options={"verbose_name": "cuenta de mesa", "verbose_name_plural": "cuentas de mesa", "ordering": ("-opened_at",)},
        ),
        migrations.AddConstraint(
            model_name="tableaccount",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "open")), fields=("table",), name="unique_open_account_per_table"),
        ),
    ]
