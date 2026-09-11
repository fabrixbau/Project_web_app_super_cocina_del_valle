# NOTA TEMPORAL PARA APRENDIZAJE:
# Un context processor agrega el contador a todas las pantallas internas sin repetir la
# consulta en cada vista. Solo consulta para Administrador o Telefonista. Borra esta nota.

from accounts.roles import ADMIN, OPERATIONAL_ROLES, ORDER_TAKER, user_has_any_role

from .models import InternalNotification, StockAlert


def notification_counter(request):
    can_view = user_has_any_role(request.user, OPERATIONAL_ROLES)
    count = 0
    if can_view:
        if user_has_any_role(request.user, (ADMIN, ORDER_TAKER)):
            count = InternalNotification.objects.filter(is_read=False).count()
        count += StockAlert.objects.filter(is_active=True).exclude(
            dismissals__user=request.user,
        ).count()
    return {
        "can_view_notifications": can_view,
        "unread_notification_count": count,
    }
