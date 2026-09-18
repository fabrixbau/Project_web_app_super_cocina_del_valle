from django.conf import settings
from django.db import models
from django.utils import timezone


class PrintStation(models.Model):
    """Estado reportado por el agente de la Dell mediante latidos periódicos.

    Sólo existe una estación (una Dell, una POS-80) por ahora, así que se usa
    una sola fila identificada por `name` en vez de modelar varias impresoras.
    """

    HEARTBEAT_TIMEOUT_SECONDS = 25

    name = models.CharField(max_length=50, unique=True, default="cocina")
    printer_available = models.BooleanField(default=False)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    @property
    def is_online(self):
        if not self.last_heartbeat_at or not self.printer_available:
            return False
        age = (timezone.now() - self.last_heartbeat_at).total_seconds()
        return age <= self.HEARTBEAT_TIMEOUT_SECONDS

    @classmethod
    def current(cls):
        station, _ = cls.objects.get_or_create(name="cocina")
        return station


class PrintJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PRINTING = "printing", "En impresión"
        PRINTED = "printed", "Enviado a impresora"
        FAILED = "failed", "Error"
        EXPIRED = "expired", "Expirado"

    source_type = models.CharField(max_length=12)
    source_id = models.PositiveBigIntegerField()
    ticket_type = models.CharField(max_length=12)
    label = models.CharField(max_length=120)
    html = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("created_at", "id")
