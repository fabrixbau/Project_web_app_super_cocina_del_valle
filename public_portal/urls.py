# NOTA TEMPORAL PARA APRENDIZAJE:
# `/pedir/menu/` apunta al catálogo público y no requiere cuenta. La vista filtra los
# productos que no estén disponibles. Borra esta nota al terminar.

from django.urls import path

from menu import views as menu_views

from . import views


app_name = "public_portal"
urlpatterns = [
    path("", views.home, name="home"),
    path("menu/", menu_views.public_menu, name="menu"),
]
