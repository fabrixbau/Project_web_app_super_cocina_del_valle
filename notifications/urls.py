# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas forman el centro interno: listar y abrir cada alerta individualmente.
# Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "notifications"
urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("pendientes/", views.notification_pending, name="notification_pending"),
    path("marcar-todas/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("<int:notification_id>/abrir/", views.notification_open, name="notification_open"),
    path("inventario/<int:alert_id>/descartar/", views.stock_alert_dismiss, name="stock_alert_dismiss"),
]
