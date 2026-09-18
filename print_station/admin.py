from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone

from .models import PrintJob, PrintStation

JOB_TTL_SECONDS = 90


@admin.register(PrintStation)
class PrintStationAdmin(admin.ModelAdmin):
    list_display = ("name", "printer_available", "last_heartbeat_at", "is_online", "last_error")
    readonly_fields = ("last_heartbeat_at", "is_online")

    @admin.display(boolean=True, description="En línea")
    def is_online(self, obj):
        return obj.is_online


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "ticket_type", "status", "created_at", "claimed_at", "completed_at")
    list_filter = ("status", "ticket_type", "created_at")
    search_fields = ("label", "error")
    readonly_fields = ("source_type", "source_id", "ticket_type", "label", "html", "requested_by", "created_at", "claimed_at", "completed_at", "error")
    actions = ("retry_jobs",)

    @admin.action(description="Reintentar trabajos (comprobar antes que no salieron en papel)")
    def retry_jobs(self, request, queryset):
        # NOTA TEMPORAL PARA APRENDIZAJE: un reintento manual debe renovar expires_at;
        # si no, un trabajo de hace horas volvería a "pending" ya vencido y el agente
        # lo expiraría de nuevo sin intentarlo. Borra esta nota después de leerla.
        count = queryset.exclude(status=PrintJob.Status.PENDING).update(
            status=PrintJob.Status.PENDING, claimed_at=None, completed_at=None, error="",
            expires_at=timezone.now() + timedelta(seconds=JOB_TTL_SECONDS),
        )
        self.message_user(request, f"{count} trabajos devueltos a pendientes. Verifica duplicados físicos.", messages.WARNING)
