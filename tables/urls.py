# NOTA TEMPORAL PARA APRENDIZAJE:
# `seleccion-menu` recibe cada tiempo elegido y permite convertir tres tiempos en paquete.
# El cierre también usa POST porque cambia la cuenta, registra el pago y libera la mesa.
# Historial es GET porque solo consulta cuentas de hoy o de la semana. Borra esta nota.
# El switch usa POST y guarda el modo de captura únicamente en la sesión del usuario.
# Las rutas nuevas agregan productos y cambian cantidades siempre mediante POST.
# Todas estas rutas viven bajo `/app/mesas/`. Las modificaciones usan POST para que abrir,
# agregar, abrir o reasignar nunca ocurra por visitar accidentalmente un enlace. Borra esta nota.

from django.urls import path

from . import views


app_name = "tables"
urlpatterns = [
    path("", views.table_map, name="table_map"),
    path("historial/", views.table_account_history, name="table_account_history"),
    path("modo-captura/", views.table_capture_mode_switch, name="table_capture_mode_switch"),
    path("<int:table_id>/abrir/", views.table_open, name="table_open"),
    path("cuentas/<int:account_id>/", views.table_detail, name="table_detail"),
    path("cuentas/<int:account_id>/imprimir/cocina/", views.table_kitchen_print, name="table_kitchen_print"),
    path("cuentas/<int:account_id>/imprimir/cocina/modificado/", views.table_kitchen_custom_print, name="table_kitchen_custom_print"),
    path("cuentas/<int:account_id>/imprimir/cobro/", views.table_payment_print, name="table_payment_print"),
    path("cuentas/<int:account_id>/productos/<int:product_id>/agregar/", views.table_item_add, name="table_item_add"),
    path("cuentas/<int:account_id>/menu-diario/<int:product_id>/agregar/", views.table_daily_order_add, name="table_daily_order_add"),
    path("cuentas/<int:account_id>/seleccion-menu/<int:product_id>/agregar/", views.table_auto_meal_add, name="table_auto_meal_add"),
    path("cuentas/<int:account_id>/seleccion-menu/<int:product_id>/restar/", views.table_auto_meal_decrease, name="table_auto_meal_decrease"),
    path("cuentas/<int:account_id>/ticket/lineas/<int:item_id>/cambiar/", views.table_item_change, name="table_item_change"),
    path("cuentas/<int:account_id>/productos/<int:product_id>/restar-estandar/", views.table_standard_product_decrease, name="table_standard_product_decrease"),
    path("cuentas/<int:account_id>/paquetes/<int:package_id>/agregar/", views.table_package_add, name="table_package_add"),
    path("cuentas/<int:account_id>/paquetes/<int:package_id>/partidas/<int:item_id>/editar/", views.table_package_edit, name="table_package_edit"),
    path("cuentas/<int:account_id>/reasignar/", views.table_reassign, name="table_reassign"),
    path("cuentas/<int:account_id>/cliente/", views.table_customer_name_update, name="table_customer_name_update"),
    path("cuentas/<int:account_id>/cerrar/", views.table_close, name="table_close"),
]
