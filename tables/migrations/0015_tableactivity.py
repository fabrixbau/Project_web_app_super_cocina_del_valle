# NOTA TEMPORAL PARA APRENDIZAJE: Esta migración crea la bitácora que separa responsable y operador real. Borra esta nota después de aplicarla.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("tables", "0014_table_account_customer_name"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="TableActivity", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("action", models.CharField(choices=[("open", "Abrió la mesa"), ("add", "Agregó producto"), ("customize", "Agregó producto modificado"), ("increase", "Aumentó cantidad"), ("decrease", "Disminuyó cantidad"), ("remove", "Eliminó partida"), ("package", "Agregó paquete"), ("package_edit", "Editó paquete"), ("reassign", "Cambió responsable"), ("customer", "Actualizó cliente"), ("close", "Cobró y cerró")], max_length=20)),
        ("description", models.CharField(blank=True, max_length=255)),
        ("quantity_delta", models.IntegerField(default=0)),
        ("metadata", models.JSONField(blank=True, default=dict)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="tables.tableaccount")),
        ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="table_activities", to=settings.AUTH_USER_MODEL)),
    ], options={"verbose_name": "movimiento de mesa", "verbose_name_plural": "movimientos de mesa", "ordering": ("created_at", "id"), "indexes": [models.Index(fields=["account", "created_at"], name="table_act_account_time")]})]
