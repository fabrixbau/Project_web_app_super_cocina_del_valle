from django.db import migrations


def create_packaging_catalog(apps, schema_editor):
    """Create safe placeholders without inventing prices for the business."""
    Category = apps.get_model("menu", "Category")
    Product = apps.get_model("menu", "Product")
    category, _ = Category.objects.get_or_create(
        name="Envases",
        defaults={
            "sort_order": 900,
            "public_breakfast_order": 900,
            "public_lunch_order": 900,
            "table_breakfast_order": 900,
            "table_lunch_order": 900,
            "show_on_public_breakfast": False,
            "show_on_public_lunch": False,
            "show_on_table_breakfast": True,
            "show_on_table_lunch": True,
        },
    )
    defaults = (
        ("Paquete de envases", "package", False, 10),
        ("Contenedor chico", "individual", False, 20),
        ("Contenedor mediano", "individual", False, 30),
        ("Contenedor grande", "individual", False, 40),
        ("Cliente trae recipientes", "customer_own", True, 50),
    )
    for name, kind, available, order in defaults:
        Product.objects.get_or_create(
            category=category,
            name=name,
            defaults={
                "price": 0,
                "description": "Indicación de empaque" if kind == "customer_own" else "Configura el precio antes de habilitarlo.",
                "is_available": available,
                "is_sold_individually": True,
                "component_type": "complement",
                "packaging_kind": kind,
                "sort_order": order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("menu", "0011_product_packaging_kind")]

    operations = [migrations.RunPython(create_packaging_catalog, migrations.RunPython.noop)]
