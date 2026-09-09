from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0020_terminalcut_transfer_provider"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerDebt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("paid_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("partial", "Pago parcial"), ("paid", "Pagado"), ("forgiven", "Condonado")], db_index=True, default="pending", max_length=15)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_debts_created", to=settings.AUTH_USER_MODEL)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="debts", to="orders.customer")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="customer_debt", to="orders.order")),
            ],
            options={"ordering": ("status", "-created_at")},
        ),
        migrations.CreateModel(
            name="CustomerDebtMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(choices=[("payment", "Abono"), ("forgive", "Condonación"), ("reopen", "Reapertura")], max_length=15)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("payment_method", models.CharField(blank=True, choices=[("cash", "Efectivo"), ("card", "Terminal"), ("transfer", "Transferencia")], max_length=20)),
                ("note", models.CharField(blank=True, max_length=250)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("debt", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="orders.customerdebt")),
                ("registered_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="customer_debt_movements", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(
            model_name="customerdebt",
            index=models.Index(fields=["customer", "status"], name="debt_customer_status_idx"),
        ),
    ]
