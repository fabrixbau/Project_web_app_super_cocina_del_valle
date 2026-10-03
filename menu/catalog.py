DAILY_WATER_CATEGORY_NAME = "bebidas frías"


def limit_cold_drinks_to_daily_water(
    categories, daily_menu, products_attribute, *, keep_package_categories=False,
):
    """Keep permanent cold drinks and only today's selected rotating water."""
    if not daily_menu or not daily_menu.water_product_id:
        return categories

    filtered_categories = []
    for category in categories:
        products = getattr(category, products_attribute, [])
        if category.name.strip().casefold() == DAILY_WATER_CATEGORY_NAME.casefold():
            products = [
                product for product in products
                if (
                    product.component_type != "daily_water"
                    or product.pk == daily_menu.water_product_id
                )
                and product.is_available
            ]
            setattr(category, products_attribute, products)
        if products or (
            keep_package_categories and getattr(category, "show_table_packages", False)
        ):
            filtered_categories.append(category)
    return filtered_categories


def public_daily_menu():
    """Menú del día publicado de hoy y sus tiempos visibles para clientes (con existencia).

    Lo usan la pizarra del menú público y la vista previa de la portada.
    """
    from django.utils import timezone

    from .inventory import filter_products_by_stock
    from .models import DailyMenu, DailyProductStock

    daily_menu = (
        DailyMenu.objects.filter(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        .select_related(
            "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
        )
        .first()
    )
    daily_groups = []
    if daily_menu:
        group_products = (
            ("Primer tiempo", (daily_menu.chicken_consomme, daily_menu.variable_first_course)),
            ("Segundo tiempo", (daily_menu.second_course_one, daily_menu.second_course_two)),
            ("Guisados", (daily_menu.chicken_stew, daily_menu.beef_stew, daily_menu.varied_stew)),
        )
        for title, products in group_products:
            visible_products = filter_products_by_stock(
                [product for product in products if product and product.is_available and product.show_to_customers],
                daily_menu=daily_menu, channel=DailyProductStock.Channel.ORDERS,
            )
            if visible_products:
                daily_groups.append({"title": title, "products": visible_products})
    return daily_menu, daily_groups
