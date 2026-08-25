# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas conectan agregar productos, carrito, checkout y confirmación. Las operaciones
# que modifican el carrito usan POST. Borra esta nota después de leerla.

from django.urls import path

from menu import views as menu_views
from orders import views as order_views

from . import views


app_name = "public_portal"
urlpatterns = [
    path("", views.home, name="home"),
    path("menu/", menu_views.public_menu, name="menu"),
    path("menu/paquete/<str:package_type>/", order_views.public_package_order, name="package_selection"),
    path("menu/producto/<int:product_id>/agregar/", order_views.public_product_add, name="product_add"),
    path("carrito/", order_views.public_cart, name="cart"),
    path("carrito/<str:key>/cantidad/", order_views.public_cart_update, name="cart_update"),
    path("carrito/<str:key>/eliminar/", order_views.public_cart_remove, name="cart_remove"),
    path("finalizar/", order_views.public_checkout, name="checkout"),
    path("confirmacion/<uuid:public_token>/", order_views.public_order_confirmation, name="order_confirmation"),
]
