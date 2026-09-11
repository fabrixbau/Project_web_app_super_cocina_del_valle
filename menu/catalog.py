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
