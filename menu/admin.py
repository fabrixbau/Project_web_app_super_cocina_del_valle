# NOTA TEMPORAL PARA APRENDIZAJE:
# Registra categorías/productos en Django Admin como herramienta de respaldo. La operación
# diaria usará `/app/menu/`. Borra esta nota al terminar.

from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "is_available", "sort_order")
    list_filter = ("category", "is_available")
    search_fields = ("name", "description")
