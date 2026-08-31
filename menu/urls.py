from django.urls import path

from . import views


app_name = "menu"
urlpatterns = [
    path("", views.configuration, name="configuration"),
    path("categorias/nueva/", views.category_create, name="category_create"),
    path("categorias/orden/", views.category_ordering, name="category_ordering"),
    path("categorias/<int:category_id>/editar/", views.category_edit, name="category_edit"),
    path("categorias/<int:category_id>/eliminar/", views.category_delete, name="category_delete"),
    path("productos/nuevo/", views.product_create, name="product_create"),
    path("ingredientes/", views.ingredient_group_library, name="ingredient_group_library"),
    path("ingredientes/nuevo/", views.shared_group_edit, name="shared_group_create"),
    path("ingredientes/<uuid:shared_key>/editar/", views.shared_group_edit, name="shared_group_edit"),
    path("productos/<int:product_id>/editar/", views.product_edit, name="product_edit"),
    path("productos/<int:product_id>/ingredientes/", views.product_customization, name="product_customization"),
    path("productos/<int:product_id>/ingredientes/grupos/nuevo/", views.option_group_form, name="option_group_create"),
    path("productos/<int:product_id>/ingredientes/grupos/pegar/", views.option_group_copy, name="option_group_copy"),
    path("productos/<int:product_id>/ingredientes/grupos/<int:group_id>/editar/", views.option_group_form, name="option_group_edit"),
    path("productos/<int:product_id>/ingredientes/grupos/<int:group_id>/eliminar/", views.option_group_delete, name="option_group_delete"),
    path("productos/<int:product_id>/ingredientes/grupos/<int:group_id>/opciones/nueva/", views.product_option_form, name="product_option_create"),
    path("productos/<int:product_id>/ingredientes/grupos/<int:group_id>/opciones/<int:option_id>/editar/", views.product_option_form, name="product_option_edit"),
    path("productos/<int:product_id>/ingredientes/grupos/<int:group_id>/opciones/<int:option_id>/eliminar/", views.product_option_delete, name="product_option_delete"),
    path("productos/<int:product_id>/disponibilidad/", views.product_toggle_availability, name="product_toggle_availability"),
    path("productos/<int:product_id>/eliminar/", views.product_delete, name="product_delete"),
    path("diario/", views.daily_menu_list, name="daily_menu_list"),
    path("diario/nuevo/", views.daily_menu_form, name="daily_menu_create"),
    path("diario/<int:daily_menu_id>/editar/", views.daily_menu_form, name="daily_menu_edit"),
    path("diario/<int:daily_menu_id>/estado/", views.daily_menu_status, name="daily_menu_status"),
    path("paquetes/", views.package_configuration, name="package_configuration"),
]
