from django.conf import settings
from django.db import models


class PrintJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PRINTING = "printing", "En impresión"
        PRINTED = "printed", "Enviado a impresora"
        FAILED = "failed", "Error"

    source_type = models.CharField(max_length=12)
    source_id = models.PositiveBigIntegerField()
    ticket_type = models.CharField(max_length=12)
    label = models.CharField(max_length=120)
    html = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("created_at", "id")
