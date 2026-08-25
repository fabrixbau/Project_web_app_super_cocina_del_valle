# NOTA TEMPORAL PARA APRENDIZAJE:
# Django usa esta clase para registrar la aplicación de pedidos y descubrir sus modelos.
# Borra esta nota después de leerla.

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"
    verbose_name = "Pedidos"
