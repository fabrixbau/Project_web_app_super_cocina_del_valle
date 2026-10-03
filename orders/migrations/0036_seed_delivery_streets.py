from django.db import migrations

# Calles de reparto (archivo calles_elegibles.txt del dueño). Los rangos se guardan de menor a
# mayor sin importar el sentido en que venían; None = toda la calle. Editable en el admin.
STREETS = [
    ("Adolfo Prieto", 601, 1260),
    ("Cda. San Borja", 3, 60),
    ("Av. Coyoacán", 500, 965),
    ("Martín Mendalde", 700, 970),
    ("Cda. Eugenia", 1, 58),
    ("Amores", 700, 1070),
    ("Manuel López Cotilla", 700, 1064),
    ("Av. Gabriel Mancera", 600, 1070),
    ("Cda. Bartolache", 1020, 1149),
    ("Providencia", 700, 1150),
    ("Cda. Agustín González de Cossío", 530, 623),
    ("Patricio Sanz", 600, 1157),
    ("San Ramón", 1, 50),
    ("Luz Saviñón", 200, 600),
    ("Torres Adalid", 1, 200),
    ("Concepción Beistegui", 200, 840),
    ("Av. Eugenia", 300, 850),
    ("Av. Colonia del Valle", 41, 450),
    ("Santa Cruz", 1, 30),
    ("San Borja", 100, 740),
    ("Av. Ángel Urraza", 300, 830),
    ("Av. Porfirio Díaz", 140, 200),
    ("Matías Romero", 1, 399),
    ("Sacramento", 111, 250),
    ("Miraflores", 130, 250),
    ("Trinidad", 200, 240),
    ("San Francisco", None, None),
]


def seed(apps, schema_editor):
    DeliveryStreet = apps.get_model("orders", "DeliveryStreet")
    if DeliveryStreet.objects.exists():
        return
    DeliveryStreet.objects.bulk_create(
        DeliveryStreet(name=name, number_from=start, number_to=end) for name, start, end in STREETS
    )


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0035_delivery_zone"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
