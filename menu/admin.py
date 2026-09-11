from django.contrib import admin

from .models import (
    Category, DailyMenu, DailyProductStock, MealPackage, Product, ProductOption,
    ProductOptionGroup, ServicePeriod, StockMovement,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "component_type", "packaging_kind", "price", "is_available", "sort_order")
    list_filter = ("category", "component_type", "packaging_kind", "service_periods", "is_available")
    search_fields = ("name", "description")


class ProductOptionInline(admin.TabularInline):
    model = ProductOption
    extra = 0


@admin.register(ProductOptionGroup)
class ProductOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "selection_type", "is_required", "sort_order")
    list_filter = ("selection_type", "is_required")
    search_fields = ("name", "product__name")
    inlines = (ProductOptionInline,)


@admin.register(ServicePeriod)
class ServicePeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "is_active", "sort_order")


@admin.register(DailyMenu)
class DailyMenuAdmin(admin.ModelAdmin):
    list_display = ("date", "status", "water_product", "published_at")
    list_filter = ("status", "date")


@admin.register(MealPackage)
class MealPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name", "package_type", "price_without_water", "price_with_water",
        "table_refill_price", "is_active",
    )


@admin.register(DailyProductStock)
class DailyProductStockAdmin(admin.ModelAdmin):
    list_display = (
        "stock_type", "date", "product", "chicken_piece", "channel", "initial_quantity",
        "available_quantity", "low_stock_threshold",
    )
    list_filter = ("stock_type", "date", "channel", "chicken_piece", "is_tracked")
    search_fields = ("product__name",)
    autocomplete_fields = ("product",)
    raw_id_fields = ("daily_menu",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "stock", "quantity", "reason", "reference_type",
        "reference_id", "actor",
    )
    list_filter = ("reason", "stock__channel", "stock__date")
    search_fields = ("stock__product__name", "note", "reference_type")
    readonly_fields = (
        "stock", "quantity", "reason", "reference_type", "reference_id",
        "note", "actor", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
