# NOTA TEMPORAL PARA APRENDIZAJE: este esquema separa la evidencia de las terminales
# de las ventas originales. TerminalMovement concilia; nunca reemplaza Order/TableAccount.
# Borra esta nota después de leerla.
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0017_rename_cash_handoff_to_settlement"),
        ("tables", "0015_tableactivity"),
    ]

    operations = [
        migrations.CreateModel(
            name="TerminalCut",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operating_date", models.DateField(default=django.utils.timezone.localdate)),
                ("provider", models.CharField(choices=[("clover", "Clover"), ("mercado_pago", "Mercado Pago")], max_length=30)),
                ("status", models.CharField(choices=[("open", "Abierto"), ("closed", "Cerrado")], default="open", max_length=10)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="terminal_cuts_closed", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-operating_date", "provider")},
        ),
        migrations.CreateModel(
            name="TerminalMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("tip_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("terminal_name_reference", models.CharField(blank=True, max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="terminal_movements_created", to=settings.AUTH_USER_MODEL)),
                ("cut", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="orders.terminalcut")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="terminal_movements", to="orders.order")),
                ("table_account", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="terminal_movements", to="tables.tableaccount")),
                ("tip_recipient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="terminal_movements_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("created_at", "id")},
        ),
        migrations.AddConstraint(
            model_name="terminalcut",
            constraint=models.UniqueConstraint(fields=("operating_date", "provider"), name="unique_terminal_cut_date_provider"),
        ),
    ]
