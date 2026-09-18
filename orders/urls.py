# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas viven bajo /app/pedidos/: una lista, un detalle y una acción POST para
# resolver pedidos pendientes. Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "orders"
urlpatterns = [
    path("", views.order_list, name="order_list"),
    path("clientes/", views.customer_list, name="customer_list"),
    path("clientes/nuevo/", views.customer_create, name="customer_create"),
    path("clientes/buscar/", views.customer_lookup, name="customer_lookup"),
    path("clientes/<int:customer_id>/editar/", views.customer_edit, name="customer_edit"),
    path("clientes/<int:customer_id>/eliminar/", views.customer_delete, name="customer_delete"),
    path("nuevo/", views.internal_order_create, name="internal_order_create"),
    path("<int:order_id>/editar/", views.internal_order_edit, name="internal_order_edit"),
    path("<int:order_id>/imprimir/cocina/", views.order_kitchen_print, name="order_kitchen_print"),
    path("<int:order_id>/imprimir/cocina/modificado/", views.order_kitchen_custom_print, name="order_kitchen_custom_print"),
    path("<int:order_id>/imprimir/cobro/", views.order_payment_print, name="order_payment_print"),
    path("<int:order_id>/editar/modo/", views.internal_order_mode_switch, name="internal_order_mode_switch"),
    path("<int:order_id>/editar/modalidad/", views.internal_order_type_switch, name="internal_order_type_switch"),
    path("<int:order_id>/editar/autoguardar-cliente/", views.internal_order_customer_autosave, name="internal_order_customer_autosave"),
    path("<int:order_id>/editar/nota/", views.internal_order_note, name="internal_order_note"),
    path("<int:order_id>/editar/partidas/<int:item_id>/nota/", views.internal_order_item_note, name="internal_order_item_note"),
    path("<int:order_id>/editar/propina/", views.internal_order_tip_update, name="internal_order_tip_update"),
    path("<int:order_id>/editar/cerrar-captura/", views.internal_order_close_capture, name="internal_order_close_capture"),
    path("<int:order_id>/editar/productos/<int:product_id>/agregar/", views.internal_order_product_add, name="internal_order_product_add"),
    path("<int:order_id>/editar/menu-diario/<int:product_id>/agregar/", views.internal_order_daily_product_add, name="internal_order_daily_product_add"),
    path("<int:order_id>/editar/armar-comida/<int:product_id>/agregar/", views.internal_order_auto_meal_add, name="internal_order_auto_meal_add"),
    path("<int:order_id>/editar/armar-comida/<int:product_id>/restar/", views.internal_order_auto_meal_decrease, name="internal_order_auto_meal_decrease"),
    path("<int:order_id>/editar/productos/<int:product_id>/restar/", views.internal_order_product_decrease, name="internal_order_product_decrease"),
    path("<int:order_id>/editar/partidas/<int:item_id>/cambiar/", views.internal_order_item_change, name="internal_order_item_change"),
    path("<int:order_id>/editar/paquetes/<int:item_id>/extras/", views.internal_order_package_extras, name="internal_order_package_extras"),
    path("<int:order_id>/editar/paquetes/<int:package_id>/agregar/", views.internal_order_package_add, name="internal_order_package_add"),
    path("<int:order_id>/", views.order_detail, name="order_detail"),
    path("<int:order_id>/resolver/", views.order_resolve, name="order_resolve"),
]
