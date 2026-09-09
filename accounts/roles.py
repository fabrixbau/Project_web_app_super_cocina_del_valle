# NOTA TEMPORAL PARA APRENDIZAJE:
# Ampliamos la matriz con `menu`. Solo Administrador puede administrarlo y todas sus
# vistas consultarán esta misma regla en backend. Borra esta nota al terminar.

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


ADMIN = "Administrador"
WAITER = "Mesero"
ORDER_TAKER = "Telefonista"
DELIVERY = "Repartidor"

OPERATIONAL_ROLES = (ADMIN, WAITER, ORDER_TAKER, DELIVERY)

SECTION_ROLE_MATRIX = {
    "tables": (ADMIN, WAITER, ORDER_TAKER),
    "orders": (ADMIN, WAITER, ORDER_TAKER),
    "customers": (ADMIN, ORDER_TAKER),
    "debts": (ADMIN, ORDER_TAKER),
    "deliveries": (ADMIN, ORDER_TAKER, DELIVERY),
    "cashier": (ADMIN,),
    "reports": (ADMIN,),
    "menu": (ADMIN,),
}


def user_has_any_role(user, allowed_roles):
    """Return True for superusers or users in at least one allowed group."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=allowed_roles).exists()


def role_required(*allowed_roles):
    """Require authentication and one of the supplied operational roles."""
    def decorator(view_function):
        @login_required
        @wraps(view_function)
        def wrapped_view(request, *args, **kwargs):
            if not user_has_any_role(request.user, allowed_roles):
                raise PermissionDenied
            return view_function(request, *args, **kwargs)

        return wrapped_view

    return decorator
