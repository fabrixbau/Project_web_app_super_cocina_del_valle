from django.db import migrations


def normalize_mexican_phone_keys(apps, schema_editor):
    Customer = apps.get_model("orders", "Customer")
    for customer in Customer.objects.all().iterator():
        digits = "".join(character for character in customer.phone if character.isdigit())
        key = digits[2:] if len(digits) == 12 and digits.startswith("52") else digits
        if customer.phone_key != key:
            Customer.objects.filter(pk=customer.pk).update(phone_key=key)


class Migration(migrations.Migration):
    dependencies = [("orders", "0024_coffeesettlement")]

    operations = [migrations.RunPython(normalize_mexican_phone_keys, migrations.RunPython.noop)]
