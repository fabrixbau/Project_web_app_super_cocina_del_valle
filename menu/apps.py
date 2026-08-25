# NOTA TEMPORAL PARA APRENDIZAJE:
# Django usa esta clase para identificar la app `menu`. Borra esta nota al terminar.

from django.apps import AppConfig


class MenuConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "menu"
