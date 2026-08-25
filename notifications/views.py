# NOTA TEMPORAL PARA APRENDIZAJE:
# El listado separa pendientes de atendidas. Las acciones de lectura usan POST porque
# modifican información y después llevan al detalle del pedido. Borra esta nota.

from django.contrib import messages
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
    return redirect("orders:order_detail", order_id=notification.order_id)


@require_POST
@role_required(ADMIN, ORDER_TAKER)
def mark_all_read(request):
    updated = InternalNotification.objects.filter(is_read=False).update(
        is_read=True, read_at=timezone.now(), read_by=request.user
    )
    messages.success(request, f"Se marcaron {updated} notificaciones como atendidas.")
    return redirect("notifications:notification_list")
