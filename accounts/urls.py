from django.urls import path

from . import views


app_name = "accounts"
urlpatterns = [
    path("pin/", views.quick_pin_setup, name="quick_pin_setup"),
    path("cambio-rapido/", views.quick_switch, name="quick_switch"),
    path("cambio-rapido/bloquear/", views.quick_lock, name="quick_lock"),
]
