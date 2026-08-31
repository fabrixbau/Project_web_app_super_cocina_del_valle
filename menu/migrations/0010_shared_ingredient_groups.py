# NOTA TEMPORAL PARA APRENDIZAJE:
# Los grupos antiguos exactamente iguales reciben la misma identidad compartida. Si existe una
# diferencia en reglas, ingredientes o cargos permanecen separados para no sobrescribir recetas.
# Puedes borrar esta explicación tras leerla, pero conserva la migración.

import uuid

from django.db import migrations, models


def assign_shared_keys(apps, schema_editor):
    Group = apps.get_model("menu", "ProductOptionGroup")
    family_keys = {}
    for group in Group.objects.prefetch_related("options").order_by("id"):
        option_signature = tuple(
            (option.name.casefold(), str(option.price_adjustment), option.replacement_pair.casefold(), option.is_default, option.is_available, option.sort_order)
            for option in group.options.all()
        )
        signature = (
            group.name.casefold(), group.selection_type, group.is_required, group.sort_order,
            option_signature,
        )
        group.shared_key = family_keys.setdefault(signature, uuid.uuid4())
        group.save(update_fields=("shared_key",))


class Migration(migrations.Migration):
    dependencies = [("menu", "0009_product_option_replacement_pair")]

    operations = [
        migrations.AddField(
            model_name="productoptiongroup",
            name="shared_key",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(assign_shared_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="productoptiongroup",
            name="shared_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, db_index=True),
        ),
        migrations.AddConstraint(
            model_name="productoptiongroup",
            constraint=models.UniqueConstraint(
                fields=("product", "shared_key"), name="unique_product_shared_option_group",
            ),
        ),
    ]
