from django.db.models import Q
from django.core.exceptions import ValidationError

from .models import Product


EGG_NAMES = ("Huevo revuelto", "Huevo estrellado")


def egg_products(existing_id=None):
    available = Q(name__in=EGG_NAMES, category__name__iexact="Plancha", is_available=True, is_sold_individually=True)
    if existing_id:
        available |= Q(pk=existing_id)
    return Product.objects.filter(available).order_by("name")


def selected_egg(value):
    if not value:
        return None
    try:
        product = egg_products().get(pk=int(value))
    except (TypeError, ValueError, Product.DoesNotExist) as error:
        raise ValidationError("Elige un huevo disponible de Plancha.") from error
    return product
