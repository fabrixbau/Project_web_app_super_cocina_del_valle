# NOTA TEMPORAL PARA APRENDIZAJE: Caja tiene rutas propias aunque trabaja sobre los
# mismos pedidos. Esto permite proteger todo el panel exclusivamente para Administrador.
# Borra esta nota después de leerla.
from django.urls import path

from . import views


app_name = "cashier"
urlpatterns = [
    path("", views.cashier_board, name="cashier_board"),
    path("propinas/", views.cashier_tip_report, name="tip_report"),
    path("propinas/detalle/<str:source>/<int:record_id>/", views.cashier_tip_detail, name="tip_detail"),
    path("cambios/", views.cashier_change_board, name="change_board"),
    path("terminales/", views.cashier_terminal_board, name="terminal_board"),
    path("terminales/movimientos/guardar/", views.cashier_terminal_movement_save, name="terminal_movement_save"),
    path("terminales/movimientos/<int:movement_id>/eliminar/", views.cashier_terminal_movement_delete, name="terminal_movement_delete"),
    path("terminales/cortes/<int:cut_id>/estado/", views.cashier_terminal_cut_status, name="terminal_cut_status"),
    path("adeudos/", views.cashier_debt_board, name="debt_board"),
    path("adeudos/registrar/", views.cashier_debt_create, name="debt_create"),
    path("adeudos/pedido/<int:order_id>/registrar/", views.cashier_order_debt_create, name="order_debt_create"),
    path("adeudos/<int:debt_id>/abonar/", views.cashier_debt_payment, name="debt_payment"),
    path("adeudos/<int:debt_id>/estado/", views.cashier_debt_status, name="debt_status"),
    path("<int:order_id>/pago/", views.cashier_payment_update, name="payment_update"),
    path("<int:order_id>/cambio-devuelto/", views.cashier_cash_settlement, name="cash_settlement"),
    path("<int:order_id>/liberar/", views.cashier_release_order, name="release_order"),
]
