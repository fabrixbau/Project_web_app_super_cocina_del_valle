"""VISTA DE PRUEBA del portal de clientes (sólo administradores).

Permite ver /pedir/ como lo vería un cliente a otra hora del día: Desayuno (9:00) o
Comida (14:00). La hora simulada vive en la sesión del administrador y la usan el menú
público, la disponibilidad de productos, el carrito y el aviso de comida anticipada.
Para retirarla: borrar este archivo, `templatetags/public_preview.py`, la vista/ruta
`preview_time` y volver a `timezone.localtime().time()` donde se llama `public_time`.
"""
from datetime import time

from django.utils import timezone

PREVIEW_SESSION_KEY = "public_preview_time"
PREVIEW_TIMES = {
    "breakfast": ("Desayuno", time(9, 0)),
    "lunch": ("Comida", time(14, 0)),
}


def public_time(session):
    """Hora del día que usa el portal: la simulada si un administrador la eligió."""
    choice = session.get(PREVIEW_SESSION_KEY) if session is not None else None
    if choice in PREVIEW_TIMES:
        return PREVIEW_TIMES[choice][1]
    return timezone.localtime().time()
