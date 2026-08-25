# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas separan el trabajo del repartidor del listado general de pedidos. Así un
# Repartidor entra a su panel sin darle acceso a funciones de Telefonista. Borra esta nota.

from django.urls import path

from . import views


app_name = "deliveries"
urlpatterns = [
    path("", views.delivery_board, name="delivery_board"),
    path("<int:order_id>/asignar/", views.delivery_assign, name="delivery_assign"),
    path("<int:order_id>/entregar/", views.delivery_complete, name="delivery_complete"),
]
