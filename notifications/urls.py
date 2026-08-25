# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas rutas forman el centro interno: lista, abrir una alerta y atender todas.
# Borra esta nota después de leerla.

from django.urls import path

from . import views


app_name = "notifications"
urlpatterns = [
    path("", views.notification_list, name="notification_list"),
    path("<int:notification_id>/abrir/", views.notification_open, name="notification_open"),
    path("atender-todas/", views.mark_all_read, name="mark_all_read"),
]
