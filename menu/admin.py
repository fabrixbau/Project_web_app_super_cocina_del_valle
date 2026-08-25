from django.contrib import admin

from .models import Category, DailyMenu, MealPackage, Product, ServicePeriod


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "sort_order")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "component_type", "price", "is_available", "sort_order")
    list_filter = ("category", "component_type", "service_periods", "is_available")
    search_fields = ("name", "description")


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
