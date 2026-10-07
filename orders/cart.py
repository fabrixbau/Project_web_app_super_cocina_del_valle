# NOTA TEMPORAL PARA APRENDIZAJE:
# La modalidad se guarda junto al carrito para preguntarla antes de mostrar el menú.
# El carrito se guarda como datos simples dentro de la sesión del navegador. Este archivo
# agrega, combina, actualiza y traduce esos datos a objetos actuales con precios del servidor.
# No crea pedidos todavía. Borra esta nota después de leerla.
# Productos personalizados se agrupan por producto + firma; el precio y las diferencias se
# recalculan con opciones vigentes antes de checkout. Borra esta nota.

from decimal import Decimal
from datetime import time
import uuid

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from menu.models import DailyMenu, MealPackage, Product
from menu.selection import resolve_product_selection


SESSION_KEY = "public_order_cart"
MODE_SESSION_KEY = "public_order_mode"
NOTE_SESSION_KEY = "public_order_note"


def _cart(session):
    return session.setdefault(SESSION_KEY, [])


def add_package(session, *, package, daily_menu, cleaned_data):
    item = {
        "key": uuid.uuid4().hex,
        "kind": "package",
        "package_id": package.pk,
        "daily_menu_id": daily_menu.pk,
        # En 2 tiempos el primer o el segundo tiempo llega vacío (None).
        "first_course_id": cleaned_data["first_course"].pk if cleaned_data.get("first_course") else None,
        "second_course_id": cleaned_data["second_course"].pk if cleaned_data.get("second_course") else None,
        "main_course_id": cleaned_data["main_course"].pk,
        "is_two_course": bool(cleaned_data.get("two_course")),
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


def add_product(session, *, product, quantity, selection):
    cart = _cart(session)
    for existing in cart:
        if (
            existing.get("kind") == "product"
            and existing.get("product_id") == product.pk
            and existing.get("configuration_signature", "") == selection["signature"]
        ):
            existing["quantity"] = min(99, existing["quantity"] + quantity)
            session.modified = True
            return
    cart.append({
        "key": uuid.uuid4().hex, "kind": "product", "product_id": product.pk,
        "option_ids": selection["option_ids"],
        "customization_comment": selection["comment"],
        "configuration_signature": selection["signature"], "quantity": quantity,
    })
    session.modified = True


def decrease_product(session, *, product, configuration_signature):
    """Resta solamente la partida del producto que comparte la firma indicada."""
    cart = _cart(session)
    for index in range(len(cart) - 1, -1, -1):
        item = cart[index]
        if (
            item.get("kind") == "product"
            and item.get("product_id") == product.pk
            and item.get("configuration_signature", "") == configuration_signature
        ):
            if item.get("quantity", 0) > 1:
                item["quantity"] -= 1
            else:
                cart.pop(index)
            session.modified = True
            return True
    return False


def cart_control_summary(session):
    cart = resolve_cart(session)
    standard_quantities = {}
    for item in cart["items"]:
        if item.get("kind") == "product" and not item["configuration"]["is_customized"]:
            product_id = str(item["product_id"])
            standard_quantities[product_id] = standard_quantities.get(product_id, 0) + item["quantity"]
    items = []
    for item in cart["items"]:
        if item["kind"] == "product":
            detail = " · ".join(filter(None, (*item["configuration"]["snapshot"].get("differences", []), item.get("item_note", ""))))
            customizable = bool(item["product"].option_groups.all())
            product_id = item["product_id"]
        else:
            # Cómo quedó armada la comida: tiempos, pieza, agua, tortillas y frijoles.
            detail = " · ".join(filter(None, (
                "2 tiempos" if item.get("is_two_course") else "",
                *(course.name for course in (item["first_course"], item["second_course"]) if course),
                f"{item['main_course'].name} ({item['chicken_piece_label'].lower()})" if item.get("chicken_piece_label") else item["main_course"].name,
                "con agua" if item.get("with_water") else "sin agua",
                "con tortillas" if item.get("tortillas") else "sin tortillas",
                "con frijoles" if item.get("beans") else "sin frijoles",
                item.get("item_note", ""),
            )))
            customizable = False
            product_id = None
        items.append({
            "key": item["key"], "kind": item["kind"], "product_id": product_id,
            "name": item["name"], "quantity": item["quantity"],
            "subtotal": f"{item['subtotal']:.2f}", "detail": detail,
            "customizable": customizable,
            "update_url": reverse("public_portal:cart_update", args=(item["key"],)),
            "remove_url": reverse("public_portal:cart_remove", args=(item["key"],)),
            "customize_url": reverse("public_portal:cart_customize", args=(item["key"], product_id)) if product_id else "",
            "note_url": reverse("public_portal:cart_item_note", args=(item["key"],)),
        })
    return {
        "count": cart["count"],
        "total_display": f"{cart['total']:.2f}",
        "standard_quantities": standard_quantities,
        "items": items,
        "note": session.get(NOTE_SESSION_KEY, ""),
    }


def set_cart_note(session, note):
    session[NOTE_SESSION_KEY] = " ".join((note or "").split())[:1000]
    session.modified = True


def update_item(session, *, key, quantity):
    for item in _cart(session):
        if item["key"] == key:
            item["quantity"] = quantity
            session.modified = True
            return True
    return False


def update_product_selection(session, *, key, product, selection):
    for item in _cart(session):
        if item.get("key") == key and item.get("kind") == "product" and item.get("product_id") == product.pk:
            item["option_ids"] = selection["option_ids"]
            item["customization_comment"] = selection["comment"]
            item["configuration_signature"] = selection["signature"]
            session.modified = True
            return True
    return False


def set_item_note(session, *, key, note):
    for item in _cart(session):
        if item.get("key") == key:
            item["item_note"] = " ".join((note or "").split())[:500]
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
    session.pop(MODE_SESSION_KEY, None)
    session.pop(NOTE_SESSION_KEY, None)
    session.modified = True


def get_order_mode(session):
    mode = session.get(MODE_SESSION_KEY)
    return mode if mode in {"pickup", "delivery"} else None


def set_order_mode(session, mode):
    session[MODE_SESSION_KEY] = mode
    session.modified = True


def product_is_orderable(product, now=None):
    if not product.is_available or not product.is_sold_individually or not product.show_to_customers:
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
    current_time = now or timezone.localtime().time()
    if current_time < time(12, 31):
        return product.category.show_on_public_breakfast or product.category.show_on_public_lunch
    return current_time <= time(18, 0) and product.category.show_on_public_lunch


def cart_has_lunch_items(cart_data):
    """True si el pedido trae comida (paquetes o productos de comida): sólo sale desde la 1 p. m."""
    daily_types = {
        Product.ComponentType.CHICKEN_CONSOMME, Product.ComponentType.VARIABLE_FIRST_COURSE,
        Product.ComponentType.SECOND_COURSE, Product.ComponentType.CHICKEN_STEW,
        Product.ComponentType.BEEF_STEW, Product.ComponentType.VARIED_STEW,
    }
    for item in cart_data["items"]:
        if item["kind"] == "package":
            return True
        product = item["product"]
        category = product.category
        if (
            product.component_type in daily_types
            or category.name.casefold().startswith("comida")
            or not category.show_on_public_breakfast
        ):
            return True
    return False


def resolve_cart(session):
    raw_items = _cart(session)
    from public_portal.preview import public_time
    now = public_time(session)
    package_ids = {item["package_id"] for item in raw_items if item.get("kind") == "package"}
    product_ids = {item["product_id"] for item in raw_items if item.get("kind") == "product"}
    packages = {item.pk: item for item in MealPackage.objects.filter(pk__in=package_ids, is_active=True)}
    products = {item.pk: item for item in Product.objects.filter(pk__in=product_ids).prefetch_related("service_periods", "option_groups__options")}
    resolved = []
    valid_keys = set()
    total = Decimal("0.00")
    for raw in raw_items:
        quantity = raw.get("quantity", 0)
        if quantity < 1 or quantity > 99:
            continue
        if raw.get("kind") == "product":
            product = products.get(raw["product_id"])
            if not product or not product_is_orderable(product, now=now):
                continue
            try:
                selection = resolve_product_selection(
                    product, raw.get("option_ids"), raw.get("customization_comment", ""),
                )
            except ValidationError:
                continue
            unit_price = selection["unit_price"]
            item = {
                **raw, "product": product,
                "name": f"{product.name} ({selection['comment']})" if selection["comment"] else product.name,
                "unit_price": unit_price,
                "configuration": selection,
            }
        else:
            package = packages.get(raw.get("package_id"))
            daily_menu = DailyMenu.objects.filter(
                pk=raw.get("daily_menu_id"), date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED
            ).select_related("water_product").first()
            first_id, second_id, main_id = (
                raw.get("first_course_id"), raw.get("second_course_id"), raw.get("main_course_id")
            )
            course_ids = [course_id for course_id in (first_id, second_id, main_id) if course_id]
            selected = Product.objects.in_bulk(course_ids)
            # 3 tiempos, o 2 tiempos válidos (primero + guisado o segundo + guisado).
            if not package or not daily_menu or not main_id or not (first_id or second_id):
                continue
            if len(selected) != len(course_ids) or any(
                not product.is_available or not product.show_to_customers for product in selected.values()
            ):
                continue
            if first_id and first_id not in {item.pk for item in daily_menu.first_course_options if item}:
                continue
            if second_id and second_id not in {item.pk for item in daily_menu.second_course_options if item}:
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
            if daily_menu.is_chicken_stew(main_id) and chicken_piece not in {"leg", "thigh"}:
                continue
            if not daily_menu.is_chicken_stew(main_id) and chicken_piece:
                continue
            unit_price = package.price_with_water if raw.get("with_water") else package.price_without_water
            item = {
                **raw, "package": package, "daily_menu": daily_menu, "name": package.name,
                "first_course": selected.get(first_id), "second_course": selected.get(second_id),
                "main_course": selected[main_id], "unit_price": unit_price,
                "is_two_course": not (first_id and second_id),
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
