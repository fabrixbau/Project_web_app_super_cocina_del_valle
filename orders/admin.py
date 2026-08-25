# NOTA TEMPORAL PARA APRENDIZAJE:
# El inline ahora distingue snapshots de paquetes y productos individuales.
# El admin permite inspeccionar temporalmente los pedidos creados mientras construimos el
# panel operativo propio. Las partidas se muestran dentro de cada pedido. Borra esta nota.

from django.contrib import admin

from .models import DailyOrderCounter, Order, OrderItem


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "item_type", "package_name_snapshot", "product_name_snapshot", "first_course_name_snapshot", "second_course_name_snapshot",
        "main_course_name_snapshot", "water_name_snapshot", "unit_price", "subtotal",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "formatted_number", "customer_name", "order_type", "status", "total", "created_at"
    )
    list_filter = ("order_type", "status", "payment_method", "operating_date")
    search_fields = ("customer_name", "phone", "street", "neighborhood")
    readonly_fields = ("public_token", "daily_number", "operating_date", "source", "total")
    inlines = (OrderItemInline,)


admin.site.register(DailyOrderCounter)
