# NOTA TEMPORAL PARA APRENDIZAJE:
# Conservamos el nombre antiguo `internal_portal:orders` como alias compatible. La ruta
# real se atiende primero desde la app orders. Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "internal_portal"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("mesas/", views.tables, name="tables"),
    path("pedidos/", views.orders, name="orders"),
    path("repartos/", views.deliveries, name="deliveries"),
    path("reportes/", views.reports, name="reports"),
]
