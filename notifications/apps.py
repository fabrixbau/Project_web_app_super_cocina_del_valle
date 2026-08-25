# NOTA TEMPORAL PARA APRENDIZAJE:
# Django usa esta configuración para registrar el centro interno de notificaciones.
# Borra esta nota después de leerla.

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Notificaciones"
