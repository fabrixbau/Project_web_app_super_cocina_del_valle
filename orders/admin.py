# NOTA TEMPORAL PARA APRENDIZAJE:
# Mostramos el repartidor y hacemos de solo lectura los datos de asignación automática.
# El inline ahora distingue snapshots de paquetes y productos individuales.
# También mostramos la bitácora de estados como solo lectura. Borra esta nota.
# El encabezado registra quién inició la atención.
# El admin permite inspeccionar temporalmente los pedidos creados mientras construimos el
# panel operativo propio. Las partidas se muestran dentro de cada pedido. Borra esta nota.

from django.contrib import admin

from .models import DailyOrderCounter, Order, OrderItem, OrderStatusHistory


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "item_type", "package_name_snapshot", "product_name_snapshot", "first_course_name_snapshot", "second_course_name_snapshot",
        "main_course_name_snapshot", "water_name_snapshot", "unit_price", "subtotal",
    )


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "changed_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "formatted_number", "customer_name", "order_type", "status", "delivery_person", "total", "created_at"
    )
    list_filter = ("order_type", "status", "payment_method", "operating_date")
    search_fields = ("customer_name", "phone", "street", "neighborhood")
    readonly_fields = (
        "public_token", "daily_number", "operating_date", "source", "total",
        "attention_started_by", "attention_started_at",
        "delivery_assigned_by", "delivery_assigned_at",
    )
    inlines = (OrderItemInline, OrderStatusHistoryInline)


admin.site.register(DailyOrderCounter)
