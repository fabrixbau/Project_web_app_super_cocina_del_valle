from django.core.exceptions import ValidationError

from .models import Product


def parse_packaging_quantities(post_data):
    """Read only known packaging quantity keys and reject fabricated values."""
    quantities = {}
    for key, raw_value in post_data.items():
        if not key.startswith("packaging_") or not key[10:].isdigit():
            continue
        try:
            quantity = int(raw_value or 0)
        except (TypeError, ValueError) as error:
            raise ValidationError("La cantidad de envases no es válida.") from error
        if quantity < 0 or quantity > 99:
            raise ValidationError("Cada tipo de envase admite entre 0 y 99 piezas.")
        if quantity:
            quantities[int(key[10:])] = quantity
    return quantities


def selected_packaging_products(quantities):
    if not quantities:
        return []
    products = Product.objects.select_for_update().filter(
        pk__in=quantities,
        is_available=True,
        is_sold_individually=True,
    ).exclude(packaging_kind=Product.PackagingKind.NONE)
    products_by_id = {product.pk: product for product in products}
    if set(products_by_id) != set(quantities):
        raise ValidationError("Uno de los envases seleccionados ya no está disponible.")
    return [(products_by_id[product_id], quantity) for product_id, quantity in quantities.items()]
