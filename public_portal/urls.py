# NOTA TEMPORAL PARA APRENDIZAJE:
# La modalidad se elige antes del menú; las demás rutas reutilizan esa decisión guardada
# en sesión. Borra esta nota después de leerla.

from django.urls import path

from menu import views as menu_views
from orders import views as order_views

from . import views


app_name = "public_portal"
urlpatterns = [
    path("", views.home, name="home"),
    path("modalidad/", order_views.public_order_mode, name="order_mode"),
    path("menu/", menu_views.public_menu, name="menu"),
    path("menu/paquete/<str:package_type>/", order_views.public_package_order, name="package_selection"),
    path("menu/producto/<int:product_id>/agregar/", order_views.public_product_add, name="product_add"),
    path("menu/producto/<int:product_id>/restar/", order_views.public_product_decrease, name="product_decrease"),
    path("carrito/", order_views.public_cart, name="cart"),
    path("carrito/<str:key>/cantidad/", order_views.public_cart_update, name="cart_update"),
    path("carrito/<str:key>/eliminar/", order_views.public_cart_remove, name="cart_remove"),
    path("carrito/<str:key>/producto/<int:product_id>/complementos/", order_views.public_cart_customize, name="cart_customize"),
    path("carrito/<str:key>/nota/", order_views.public_cart_item_note, name="cart_item_note"),
    path("carrito/nota/", order_views.public_cart_note, name="cart_note"),
    path("finalizar/", order_views.public_checkout, name="checkout"),
    path("confirmacion/<uuid:public_token>/", order_views.public_order_confirmation, name="order_confirmation"),
]
