# NOTA TEMPORAL PARA APRENDIZAJE:
# InternalNotification es una alerta operativa compartida. En este primer bloque apunta a
# un pedido web y registra cuándo y quién la atendió. Borra esta nota después de leerla.

from django.conf import settings
from django.db import models

from orders.models import Order


class InternalNotification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_PUBLIC_ORDER = "new_public_order", "Nuevo pedido web"

    notification_type = models.CharField(max_length=40, choices=NotificationType.choices)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="read_internal_notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_read", "-created_at"]

    def __str__(self):
        return self.title
