# NOTA TEMPORAL PARA APRENDIZAJE:
# Django usa esta configuración para registrar el módulo de mesas dentro del proyecto.
# Borra esta nota después de leerla.

from django.apps import AppConfig


class TablesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tables"
    verbose_name = "Mesas"
