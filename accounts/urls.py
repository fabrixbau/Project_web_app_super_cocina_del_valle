from django.urls import path

from . import views


app_name = "accounts"
urlpatterns = [
    path("cambio-rapido/", views.quick_switch, name="quick_switch"),
    path("cambio-rapido/bloquear/", views.quick_lock, name="quick_lock"),
]
