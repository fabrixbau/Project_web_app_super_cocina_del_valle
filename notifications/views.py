# NOTA TEMPORAL PARA APRENDIZAJE:
# Abrir una alerta registra también quién inició la atención del pedido. Se retiró la
# acción masiva para que cada alerta tenga un responsable explícito. Borra esta nota.

from datetime import timedelta

from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, OPERATIONAL_ROLES, ORDER_TAKER, role_required, user_has_any_role

from .models import InternalNotification, StockAlert, StockAlertDismissal


@role_required(*OPERATIONAL_ROLES)
def notification_list(request):
    show = request.GET.get("show", "unread")
    # NOTA TEMPORAL PARA APRENDIZAJE: esta bandeja siempre muestra sólo el día que se
    # está operando — una alerta de un pedido de hace una semana ya no tiene sentido
    # aquí. El filtro de leída/no leída sigue funcionando dentro de hoy. Borra esta
    # nota después de leerla.
    # Se muestran las de hoy y, además, las que sigan sin leer de días anteriores (con su
    # fecha), para que el contador siempre coincida con lo que se ve en la lista.
    notifications = InternalNotification.objects.filter(
        Q(created_at__date=timezone.localdate()) | Q(is_read=False),
    ).select_related("order", "order__agenda_customer", "read_by").order_by("is_read", "-created_at")
    if not user_has_any_role(request.user, (ADMIN, ORDER_TAKER)):
        notifications = notifications.none()
    if show != "all":
        notifications = notifications.filter(is_read=False)
        show = "unread"
    stock_alerts = StockAlert.objects.filter(is_active=True).select_related("stock__product")
    if request.user.is_authenticated:
        stock_alerts = stock_alerts.exclude(dismissals__user=request.user)
    return render(request, "notifications/notification_list.html", {
        "notifications": notifications, "stock_alerts": stock_alerts, "show": show,
        # Fechas locales como texto para marcar "De ayer" / "Del dd/mm/aaaa".
        "today_key": timezone.localdate().isoformat(),
        "yesterday_key": (timezone.localdate() - timedelta(days=1)).isoformat(),
    })


@role_required(ADMIN, ORDER_TAKER)
def notification_pending(request):
    """Estado para la alerta de pedidos (order-alert.js): pedidos web sin atender, total del
    contador y la notificación más reciente (para sonar sólo cuando llega una nueva)."""
    from .context_processors import notification_counts

    orders, total = notification_counts(request.user)
    latest = InternalNotification.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
    return JsonResponse({"pending": orders, "total": total, "latest": latest})


@require_POST
@role_required(*OPERATIONAL_ROLES)
def notification_open(request, notification_id):
    notification = get_object_or_404(InternalNotification, pk=notification_id)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.read_by = request.user
        notification.save(update_fields=["is_read", "read_at", "read_by"])
    if notification.order.attention_started_at is None:
        notification.order.attention_started_at = timezone.now()
        notification.order.attention_started_by = request.user
        notification.order.save(update_fields=[
            "attention_started_at", "attention_started_by", "updated_at",
        ])
    return redirect("orders:order_detail", order_id=notification.order_id)


@require_POST
@role_required(*OPERATIONAL_ROLES)
def stock_alert_dismiss(request, alert_id):
    alert = get_object_or_404(StockAlert, pk=alert_id, is_active=True)
    StockAlertDismissal.objects.get_or_create(alert=alert, user=request.user)
    return redirect("notifications:notification_list")
