# NOTA TEMPORAL PARA APRENDIZAJE:
# Relaciona las URLs internas con vistas CRUD. Los nombres permiten generar enlaces
# sin escribir rutas manuales. Borra esta nota al terminar.

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
]
