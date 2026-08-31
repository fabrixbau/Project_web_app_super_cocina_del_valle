# NOTA TEMPORAL PARA APRENDIZAJE:
# Las comandas y sus consumos aparecen agrupados para facilitar su inspección.
# El administrador de Django sirve como respaldo para consultar/desactivar mesas y revisar
# cuentas mientras construimos toda la operación en el panel propio. Borra esta nota.

from django.contrib import admin

from .models import DiningTable, TableAccount, TableAccountItem, TableCommand


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ("name", "map_row", "map_column", "display_order", "is_active")
    list_editable = ("map_row", "map_column", "display_order", "is_active")
    ordering = ("display_order", "name")


class TableAccountItemInline(admin.TabularInline):
    model = TableAccountItem
    extra = 0
    readonly_fields = ("product_name_snapshot", "unit_price", "subtotal", "added_by", "added_at")


@admin.register(TableAccount)
class TableAccountAdmin(admin.ModelAdmin):
    list_display = ("table", "status", "assigned_waiter", "opened_by", "opened_at")
    list_filter = ("status",)
    readonly_fields = ("opened_at", "closed_at")
    inlines = (TableAccountItemInline,)


class TableCommandItemInline(admin.TabularInline):
    model = TableAccountItem
    fk_name = "command"
    extra = 0
    can_delete = False
    readonly_fields = ("product_name_snapshot", "unit_price", "quantity", "subtotal")


@admin.register(TableCommand)
class TableCommandAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "created_by", "created_at")
    readonly_fields = ("account", "created_by", "created_at")
    inlines = (TableCommandItemInline,)
