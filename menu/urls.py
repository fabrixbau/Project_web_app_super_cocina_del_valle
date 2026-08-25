# NOTA TEMPORAL PARA APRENDIZAJE:
# Sumamos rutas para listar, crear, editar y cambiar el estado del menú diario.
# Publicar/cerrar usa POST para evitar cambios accidentales desde un enlace. Borra esta nota.

from django.urls import path

from . import views


app_name = "menu"
urlpatterns = [
    path("", views.configuration, name="configuration"),
    path("categorias/nueva/", views.category_create, name="category_create"),
    path("categorias/<int:category_id>/editar/", views.category_edit, name="category_edit"),
    path("categorias/<int:category_id>/eliminar/", views.category_delete, name="category_delete"),
    path("productos/nuevo/", views.product_create, name="product_create"),
    path("productos/<int:product_id>/editar/", views.product_edit, name="product_edit"),
    path("productos/<int:product_id>/disponibilidad/", views.product_toggle_availability, name="product_toggle_availability"),
    path("productos/<int:product_id>/eliminar/", views.product_delete, name="product_delete"),
    path("diario/", views.daily_menu_list, name="daily_menu_list"),
    path("diario/nuevo/", views.daily_menu_form, name="daily_menu_create"),
    path("diario/<int:daily_menu_id>/editar/", views.daily_menu_form, name="daily_menu_edit"),
    path("diario/<int:daily_menu_id>/estado/", views.daily_menu_status, name="daily_menu_status"),
]
