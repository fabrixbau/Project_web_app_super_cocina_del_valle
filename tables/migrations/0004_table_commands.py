# NOTA TEMPORAL PARA APRENDIZAJE:
# TableCommand agrupa las líneas confirmadas en una misma ronda. La relación es opcional
# para conservar los consumos creados durante las pruebas anteriores. Borra esta nota.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tables", "0003_table_account_items"),
    ]
    operations = [
        migrations.CreateModel(
            name="TableCommand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="commands", to="tables.tableaccount")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="table_commands_created", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "comanda de mesa", "verbose_name_plural": "comandas de mesa", "ordering": ("created_at", "id")},
        ),
        migrations.AddField(
            model_name="tableaccountitem", name="command",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="items", to="tables.tablecommand"),
        ),
    ]
