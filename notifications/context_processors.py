# NOTA TEMPORAL PARA APRENDIZAJE:
# Un context processor agrega el contador a todas las pantallas internas sin repetir la
# consulta en cada vista. Solo consulta para Administrador o Telefonista. Borra esta nota.

from accounts.roles import ADMIN, ORDER_TAKER, user_has_any_role

from .models import InternalNotification


def notification_counter(request):
    can_view = user_has_any_role(request.user, (ADMIN, ORDER_TAKER))
    return {
        "can_view_notifications": can_view,
        "unread_notification_count": InternalNotification.objects.filter(is_read=False).count() if can_view else 0,
    }
