from django.contrib import admin, messages

from .models import PrintJob


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "ticket_type", "status", "created_at", "claimed_at", "completed_at")
    list_filter = ("status", "ticket_type", "created_at")
    search_fields = ("label", "error")
    readonly_fields = ("source_type", "source_id", "ticket_type", "label", "html", "requested_by", "created_at", "claimed_at", "completed_at", "error")
    actions = ("retry_jobs",)

    @admin.action(description="Reintentar trabajos (comprobar antes que no salieron en papel)")
    def retry_jobs(self, request, queryset):
        count = queryset.exclude(status=PrintJob.Status.PENDING).update(
            status=PrintJob.Status.PENDING, claimed_at=None, completed_at=None, error=""
        )
        self.message_user(request, f"{count} trabajos devueltos a pendientes. Verifica duplicados físicos.", messages.WARNING)
