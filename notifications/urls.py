# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas forman el centro interno: listar y abrir cada alerta individualmente.
# Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "notifications"
urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("<int:notification_id>/abrir/", views.notification_open, name="notification_open"),
]
