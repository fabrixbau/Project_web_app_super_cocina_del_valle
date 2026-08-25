# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas viven bajo /app/pedidos/: una lista, un detalle y una acción POST para
# resolver pedidos pendientes. Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "orders"
urlpatterns = [
    path("", views.order_list, name="order_list"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/resolver/", views.order_resolve, name="order_resolve"),
]
