# NOTA TEMPORAL PARA APRENDIZAJE:
# Un context processor agrega el contador a todas las pantallas internas sin repetir la
# consulta en cada vista. Solo consulta para Administrador o Telefonista. Borra esta nota.

from accounts.roles import ADMIN, OPERATIONAL_ROLES, ORDER_TAKER, user_has_any_role

from .models import InternalNotification, StockAlert


def notification_counts(user):
    """(pedidos web sin atender, total del contador) para el usuario.

    Sólo Administrador y Telefonista ven los pedidos web; las alertas de existencias suman
    al contador pero no hacen parpadear la pantalla.
    """
    orders = 0
    if user_has_any_role(user, (ADMIN, ORDER_TAKER)):
        orders = InternalNotification.objects.filter(is_read=False).count()
    stock = StockAlert.objects.filter(is_active=True).exclude(dismissals__user=user).count()
    return orders, orders + stock


def notification_counter(request):
    can_view = user_has_any_role(request.user, OPERATIONAL_ROLES)
    orders = count = 0
    if can_view:
        orders, count = notification_counts(request.user)
    return {
        "can_view_notifications": can_view,
        "unread_notification_count": count,
        # Administrador y Telefonista: marco amarillo parpadeando mientras haya pedidos web
        # sin atender (static/js/order-alert.js revisa cada 15 s).
        "can_receive_order_alerts": user_has_any_role(request.user, (ADMIN, ORDER_TAKER)),
        # Sólo Administrador registra "No pagó"; la base incluye su panel de cliente.
        "user_is_admin": user_has_any_role(request.user, (ADMIN,)),
        "pending_order_notification_count": orders,
    }
