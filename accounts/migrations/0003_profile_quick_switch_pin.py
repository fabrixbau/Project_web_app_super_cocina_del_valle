# NOTA TEMPORAL PARA APRENDIZAJE:
# Estos campos guardan el hash del PIN y protecciones contra intentos repetidos. Ningún PIN
# existente se inventa durante la migración; cada mesero lo configura personalmente.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_create_operational_roles")]
    operations = [
        migrations.AddField(model_name="profile", name="quick_pin_hash", field=models.CharField(blank=True, max_length=128)),
        migrations.AddField(model_name="profile", name="pin_failed_attempts", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="profile", name="pin_locked_until", field=models.DateTimeField(blank=True, null=True)),
    ]
