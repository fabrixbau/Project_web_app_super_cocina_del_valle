from django.urls import path

from menu import views as menu_views

from . import views


app_name = "public_portal"
urlpatterns = [
    path("", views.home, name="home"),
    path("menu/", menu_views.public_menu, name="menu"),
    path("menu/paquete/<str:package_type>/", menu_views.package_selection, name="package_selection"),
]
