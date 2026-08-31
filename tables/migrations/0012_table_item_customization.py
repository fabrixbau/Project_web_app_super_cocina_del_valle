# NOTA TEMPORAL PARA APRENDIZAJE:
# La mesa conserva la receta elegida aunque después cambien ingredientes del producto.
# La firma evita mezclar en una sola línea preparaciones diferentes. Borra esta nota.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tables", "0011_rename_card_label_to_terminal")]

    operations = [
        migrations.AddField(model_name="tableaccountitem", name="configuration_snapshot", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="tableaccountitem", name="configuration_signature", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="tableaccountitem", name="is_customized", field=models.BooleanField(default=False)),
    ]
