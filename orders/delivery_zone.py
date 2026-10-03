"""Zona de reparto: ¿la calle y el número del cliente están en las calles de reparto?

Sólo importan la calle y el número (no la colonia). La comparación ignora acentos,
mayúsculas, puntos y prefijos como "Av."/"Avenida"/"Calle"; "Cerrada" equivale a "Cda.".
"""
import re
import unicodedata

from .models import DeliveryStreet

_PREFIXES = {"av", "avenida", "calle", "c"}
_ALIASES = {"cerrada": "cda", "sta": "santa", "gonzales": "gonzalez", "cosio": "cossio"}


def normalize_street(value):
    text = unicodedata.normalize("NFD", str(value or "")).encode("ascii", "ignore").decode().lower()
    words = [_ALIASES.get(word, word) for word in re.findall(r"[a-z0-9]+", text)]
    while words and words[0] in _PREFIXES:
        words = words[1:]
    return " ".join(words)


def street_number(value):
    match = re.search(r"\d+", str(value or ""))
    return int(match.group()) if match else None


def street_choices():
    """Nombres para las sugerencias del formulario."""
    return list(DeliveryStreet.objects.filter(is_active=True).values_list("name", flat=True))


def is_in_delivery_zone(street, exterior_number):
    key = normalize_street(street)
    if not key:
        return False
    number = street_number(exterior_number)
    for candidate in DeliveryStreet.objects.filter(is_active=True):
        if normalize_street(candidate.name) != key:
            continue
        if candidate.number_from is None or candidate.number_to is None:
            return True
        if number is not None and min(candidate.number_from, candidate.number_to) <= number <= max(candidate.number_from, candidate.number_to):
            return True
    return False
