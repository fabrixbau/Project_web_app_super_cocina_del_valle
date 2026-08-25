# NOTA TEMPORAL PARA APRENDIZAJE:
# El carrito se guarda como datos simples dentro de la sesión del navegador. Este archivo
# agrega, combina, actualiza y traduce esos datos a objetos actuales con precios del servidor.
# No crea pedidos todavía. Borra esta nota después de leerla.

from decimal import Decimal
import uuid

from django.utils import timezone

from menu.models import DailyMenu, MealPackage, Product


SESSION_KEY = "public_order_cart"


def _cart(session):
    return session.setdefault(SESSION_KEY, [])


def add_package(session, *, package, daily_menu, cleaned_data):
    item = {
        "key": uuid.uuid4().hex,
        "kind": "package",
        "package_id": package.pk,
        "daily_menu_id": daily_menu.pk,
        "first_course_id": cleaned_data["first_course"].pk,
        "second_course_id": cleaned_data["second_course"].pk,
        "main_course_id": cleaned_data["main_course"].pk,
        "chicken_piece": cleaned_data["chicken_piece"],
        "with_water": cleaned_data["with_water"],
        "tortillas": cleaned_data["tortillas"] == "yes",
        "beans": cleaned_data["beans"] == "yes",
        "quantity": cleaned_data["quantity"],
    }
    signature_fields = tuple(key for key in item if key not in {"key", "quantity"})
    cart = _cart(session)
    for existing in cart:
        if all(existing.get(key) == item[key] for key in signature_fields):
            existing["quantity"] = min(99, existing["quantity"] + item["quantity"])
            session.modified = True
            return
    cart.append(item)
    session.modified = True


def add_product(session, *, product, quantity):
    cart = _cart(session)
    for existing in cart:
        if existing.get("kind") == "product" and existing.get("product_id") == product.pk:
            existing["quantity"] = min(99, existing["quantity"] + quantity)
            session.modified = True
            return
    cart.append({"key": uuid.uuid4().hex, "kind": "product", "product_id": product.pk, "quantity": quantity})
    session.modified = True


def update_item(session, *, key, quantity):
    for item in _cart(session):
        if item["key"] == key:
            item["quantity"] = quantity
            session.modified = True
            return True
    return False


def remove_item(session, *, key):
    cart = _cart(session)
    new_cart = [item for item in cart if item["key"] != key]
    if len(new_cart) != len(cart):
        session[SESSION_KEY] = new_cart
        session.modified = True
        return True
    return False


def clear(session):
    session.pop(SESSION_KEY, None)
    session.modified = True


def product_is_orderable(product):
    if not product.is_available or not product.is_sold_individually:
        return False
    daily_types = {
        Product.ComponentType.CHICKEN_CONSOMME, Product.ComponentType.VARIABLE_FIRST_COURSE,
        Product.ComponentType.SECOND_COURSE, Product.ComponentType.CHICKEN_STEW,
        Product.ComponentType.BEEF_STEW, Product.ComponentType.VARIED_STEW,
    }
    if product.component_type in daily_types:
        menu = DailyMenu.objects.filter(
            date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED
        ).first()
        if not menu or product.pk not in {
            *(item.pk for item in menu.first_course_options if item),
            *(item.pk for item in menu.second_course_options if item),
            *(item.pk for item in menu.stew_options if item),
        }:
            return False
    periods = list(product.service_periods.all())
    current_time = timezone.localtime().time()
    return not periods or any(period.contains(current_time) for period in periods)


def resolve_cart(session):
    raw_items = _cart(session)
    package_ids = {item["package_id"] for item in raw_items if item.get("kind") == "package"}
    product_ids = {item["product_id"] for item in raw_items if item.get("kind") == "product"}
    packages = {item.pk: item for item in MealPackage.objects.filter(pk__in=package_ids, is_active=True)}
    products = {item.pk: item for item in Product.objects.filter(pk__in=product_ids).prefetch_related("service_periods")}
    resolved = []
    valid_keys = set()
    total = Decimal("0.00")
    for raw in raw_items:
        quantity = raw.get("quantity", 0)
        if quantity < 1 or quantity > 99:
            continue
        if raw.get("kind") == "product":
            product = products.get(raw["product_id"])
            if not product or not product_is_orderable(product):
                continue
            unit_price = product.price
            item = {**raw, "product": product, "name": product.name, "unit_price": unit_price}
        else:
            package = packages.get(raw.get("package_id"))
            daily_menu = DailyMenu.objects.filter(
                pk=raw.get("daily_menu_id"), date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED
            ).select_related("water_product").first()
            selected = Product.objects.in_bulk([
                raw.get("first_course_id"), raw.get("second_course_id"), raw.get("main_course_id")
            ])
            if not package or not daily_menu or len(selected) != 3 or any(not product.is_available for product in selected.values()):
                continue
            first_id, second_id, main_id = (
                raw["first_course_id"], raw["second_course_id"], raw["main_course_id"]
            )
            if first_id not in {item.pk for item in daily_menu.first_course_options if item}:
                continue
            if second_id not in {item.pk for item in daily_menu.second_course_options if item}:
                continue
            if package.package_type == MealPackage.PackageType.RUNNING:
                if main_id not in {item.pk for item in daily_menu.stew_options if item}:
                    continue
            elif not (
                selected[main_id].component_type == Product.ComponentType.GRILL
                and selected[main_id].eligible_for_executive_meal
            ):
                continue
            chicken_piece = raw.get("chicken_piece", "")
            if main_id == daily_menu.chicken_stew_id and chicken_piece not in {"leg", "thigh"}:
                continue
            if main_id != daily_menu.chicken_stew_id and chicken_piece:
                continue
            unit_price = package.price_with_water if raw.get("with_water") else package.price_without_water
            item = {
                **raw, "package": package, "daily_menu": daily_menu, "name": package.name,
                "first_course": selected[raw["first_course_id"]],
                "second_course": selected[raw["second_course_id"]],
                "main_course": selected[raw["main_course_id"]], "unit_price": unit_price,
                "chicken_piece_label": {"leg": "Pierna", "thigh": "Muslo"}.get(chicken_piece, ""),
            }
        item["subtotal"] = unit_price * quantity
        total += item["subtotal"]
        resolved.append(item)
        valid_keys.add(raw["key"])
    return {
        "items": resolved, "total": total,
        "count": sum(item["quantity"] for item in resolved),
        "invalid_count": len(raw_items) - len(resolved),
        "invalid_items": [item for item in raw_items if item.get("key") not in valid_keys],
    }
