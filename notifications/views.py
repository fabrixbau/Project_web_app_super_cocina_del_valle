# NOTA TEMPORAL PARA APRENDIZAJE:
# Abrir una alerta registra también quién inició la atención del pedido. Se retiró la
# acción masiva para que cada alerta tenga un responsable explícito. Borra esta nota.

from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, ORDER_TAKER, role_required

from .models import InternalNotification


@role_required(ADMIN, ORDER_TAKER)
def notification_list(request):
    show = request.GET.get("show", "unread")
    notifications = InternalNotification.objects.select_related("order", "read_by")
    if show != "all":
        notifications = notifications.filter(is_read=False)
        show = "unread"
    return render(request, "notifications/notification_list.html", {
        "notifications": notifications, "show": show,
    })


@require_POST
@role_required(ADMIN, ORDER_TAKER)
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
