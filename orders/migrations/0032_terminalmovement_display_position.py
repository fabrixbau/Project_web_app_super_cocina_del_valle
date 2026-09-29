from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0031_terminalmovement_classification_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="terminalmovement",
            name="display_position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="terminalmovement",
            options={"ordering": ("display_position", "created_at", "id")},
        ),
    ]
