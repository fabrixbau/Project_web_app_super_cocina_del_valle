# NOTA TEMPORAL PARA APRENDIZAJE: Caja tiene rutas propias aunque trabaja sobre los
# mismos pedidos. Esto permite proteger todo el panel exclusivamente para Administrador.
# Borra esta nota después de leerla.
from django.urls import path

from . import views


app_name = "cashier"
urlpatterns = [
    path("", views.cashier_board, name="cashier_board"),
    path("<int:order_id>/pago/", views.cashier_payment_update, name="payment_update"),
    path("<int:order_id>/cambio-entregado/", views.cashier_cash_handoff, name="cash_handoff"),
]
