# NOTA TEMPORAL PARA APRENDIZAJE:
# Registramos alertas en admin para diagnóstico; la operación normal usa /app/notificaciones/.
# Borra esta nota después de leerla.

from django.contrib import admin

from .models import InternalNotification, StockAlert, StockAlertDismissal


@admin.register(InternalNotification)
class InternalNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "is_read", "read_by", "created_at")
    list_filter = ("notification_type", "is_read", "created_at")
    search_fields = ("title", "message", "order__customer_name", "order__phone")


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ("stock", "available_quantity", "is_active", "triggered_at", "resolved_at")
    list_filter = ("is_active", "stock__date", "stock__channel")


@admin.register(StockAlertDismissal)
class StockAlertDismissalAdmin(admin.ModelAdmin):
    list_display = ("alert", "user", "dismissed_at")
