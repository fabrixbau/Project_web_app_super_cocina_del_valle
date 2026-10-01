# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta es la regla compartida por clientes y Mesas. Recibe opciones seleccionadas, comprueba
# que pertenecen al producto y calcula precio, firma, snapshot y diferencias contra la receta
# estándar. Así ambos canales cobran y describen exactamente igual. Borra esta nota.

import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import QueryDict

from .models import Product, ProductOptionGroup


MAX_CUSTOMIZED_PIECES = 99


def requested_customizations(post):
    """Piezas pedidas en un envío como [(raw_option_ids, comentario, cantidad)].

    Sin personalización devuelve una pieza estándar (opciones None). Con el contador
    de la ficha de Personalizar llegan varias configuraciones en `customization_batch`
    (JSON); las piezas idénticas vienen agrupadas en una sola entrada con su cantidad.
    """
    if post.get("customization_selected") != "1":
        return [(None, "", 1)]
    raw_batch = post.get("customization_batch")
    if not raw_batch:
        return [(post.getlist("option_ids"), post.get("customization_comment", ""), 1)]
    invalid = ValidationError("La personalización recibida no es válida.")
    try:
        batch = json.loads(raw_batch)
    except ValueError as error:
        raise invalid from error
    if not isinstance(batch, list) or not batch:
        raise invalid
    pieces = []
    for entry in batch:
        if not isinstance(entry, dict):
            raise invalid
        quantity = entry.get("quantity")
        option_ids = entry.get("option_ids", [])
        comment = entry.get("comment", "")
        if (
            isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1
            or not isinstance(option_ids, list) or not isinstance(comment, str)
        ):
            raise invalid
        pieces.append(([str(option_id) for option_id in option_ids], comment, quantity))
    if sum(quantity for _, _, quantity in pieces) > MAX_CUSTOMIZED_PIECES:
        raise ValidationError(f"Puedes agregar hasta {MAX_CUSTOMIZED_PIECES} piezas a la vez.")
    return pieces


def expanded_customizations(post):
    """Igual que `requested_customizations`, pero con una entrada por pieza."""
    return [
        (option_ids, comment)
        for option_ids, comment, quantity in requested_customizations(post)
        for _ in range(quantity)
    ]


def requested_packages(post):
    """Paquetes pedidos desde el diálogo como [(datos_del_formulario, cantidad)].

    Con el contador del diálogo llegan varios paquetes en `package_batch` (JSON
    `[{"fields": [[nombre, valor], ...], "quantity": n}]`); los idénticos vienen
    agrupados. Sin lote, el propio envío es un único paquete.
    """
    raw_batch = post.get("package_batch")
    if not raw_batch:
        return [(post, 1)]
    invalid = ValidationError("Los paquetes recibidos no son válidos.")
    try:
        batch = json.loads(raw_batch)
    except ValueError as error:
        raise invalid from error
    if not isinstance(batch, list) or not batch:
        raise invalid
    packages = []
    for entry in batch:
        if not isinstance(entry, dict):
            raise invalid
        quantity = entry.get("quantity")
        fields = entry.get("fields")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1 or not isinstance(fields, list):
            raise invalid
        data = QueryDict(mutable=True)
        for field in fields:
            if not (isinstance(field, list) and len(field) == 2 and all(isinstance(part, str) for part in field)):
                raise invalid
            data.appendlist(*field)
        packages.append((data, quantity))
    if sum(quantity for _, quantity in packages) > MAX_CUSTOMIZED_PIECES:
        raise ValidationError(f"Puedes agregar hasta {MAX_CUSTOMIZED_PIECES} paquetes a la vez.")
    return packages


PACKAGE_COURSE_FIELDS = ("first_course", "second_course", "main_course")
TICKET_COMMENT_LIMIT = 150


def fit_ticket_comment(text, limit=TICKET_COMMENT_LIMIT):
    """Recorta un comentario compuesto al largo que admite la partida del ticket."""
    return text if len(text) <= limit else f"{text[:limit - 1].rstrip()}…"


def describe_component(name, differences, comment=""):
    """'Producto: Sin cebolla · comentario' para un tiempo modificado, o '' si no lo está."""
    details = " · ".join(filter(None, (*differences, comment)))
    return f"{name}: {details}" if details else ""


def ticket_modifications(item, *, is_package):
    """Líneas que muestran en el ticket cómo quedó modificada una partida.

    Productos: sus cambios de ingredientes en una línea (el comentario ya va junto al
    nombre). Paquetes: un renglón por cada tiempo personalizado.
    """
    snapshot = item.configuration_snapshot or {}
    if is_package:
        return [line for line in snapshot.get("components", []) if line]
    differences = [label for label in snapshot.get("differences", []) if label]
    return [" · ".join(differences)] if differences else []


def ticket_item_name(base_name, item, *, is_package):
    """Nombre en el ticket. Si los tiempos del paquete ya se listan aparte, entre
    paréntesis sólo queda el comentario general del paquete."""
    snapshot = item.configuration_snapshot or {}
    comment = item.customization_comment
    if is_package and snapshot.get("components"):
        comment = snapshot.get("package_comment", "")
    return f"{base_name} ({comment})" if comment else base_name




def apply_package_component_customizations(data, cleaned_data, *, comment_limit=TICKET_COMMENT_LIMIT):
    """Suma al paquete la personalización de cada tiempo elegida con la ficha.

    `component_customizations` llega como JSON `{campo: {product_id, option_ids, comment}}`.
    Sólo cuenta la del producto que quedó elegido en ese tiempo. Igual que las comidas
    armadas desde la categoría, cada tiempo se describe como "Producto: diferencias" en
    el comentario del paquete y los ingredientes con costo se suman como recargo.
    Devuelve False si no había personalización que aplicar.
    """
    raw = data.get("component_customizations")
    if not raw:
        return False
    try:
        requested = json.loads(raw)
    except ValueError as error:
        raise ValidationError("La personalización de los tiempos no es válida.") from error
    if not isinstance(requested, dict):
        raise ValidationError("La personalización de los tiempos no es válida.")
    descriptions = []
    surcharge = Decimal("0.00")
    for field_name in PACKAGE_COURSE_FIELDS:
        product = cleaned_data.get(field_name)
        entry = requested.get(field_name)
        if not product or not isinstance(entry, dict) or str(entry.get("product_id")) != str(product.pk):
            continue
        option_ids = entry.get("option_ids", [])
        if not isinstance(option_ids, list) or not isinstance(entry.get("comment", ""), str):
            raise ValidationError("La personalización de los tiempos no es válida.")
        product = product_with_options_queryset(Product.objects).get(pk=product.pk)
        selection = resolve_product_selection(product, option_ids, entry.get("comment", ""))
        if not selection["is_customized"]:
            continue
        descriptions.append(describe_component(product.name, selection["difference_labels"], selection["comment"]))
        surcharge += max(selection["additional_price"], Decimal("0.00"))
    if not descriptions:
        return False
    package_comment = cleaned_data.get("customization_comment", "")
    comment = " · ".join(filter(None, (*descriptions, package_comment)))
    if len(comment) > comment_limit:
        raise ValidationError(
            "La personalización del paquete es demasiado larga para el ticket; acorta los comentarios."
        )
    cleaned_data["customization_comment"] = comment
    cleaned_data["customization_surcharge"] = surcharge
    cleaned_data["configuration_signature"] = f"comentarios:{comment.casefold()}|extra:{surcharge}"
    cleaned_data["configuration_snapshot"] = {
        "comment": comment, "components": descriptions, "package_comment": package_comment,
        "surcharge": str(surcharge),
    }
    cleaned_data["is_customized"] = True
    return True


def product_with_options_queryset(queryset):
    return queryset.prefetch_related("option_groups__options")


def default_option_ids(product):
    return {
        option.pk
        for group in product.option_groups.all()
        for option in group.options.all()
        if option.is_available and option.is_default
    }


def resolve_product_selection(product, raw_option_ids=None, raw_comment=""):
    comment = " ".join(str(raw_comment or "").split())
    if len(comment) > 150:
        raise ValidationError("El comentario de preparación no puede superar 150 caracteres.")
    groups = list(product.option_groups.all())
    available_by_id = {
        option.pk: option
        for group in groups
        for option in group.options.all()
        if option.is_available
    }
    if raw_option_ids is None:
        selected_ids = default_option_ids(product)
    else:
        try:
            selected_ids = {int(value) for value in raw_option_ids}
        except (TypeError, ValueError) as error:
            raise ValidationError("La personalización contiene una opción inválida.") from error
    if not selected_ids.issubset(available_by_id):
        raise ValidationError("Una opción seleccionada ya no está disponible para este producto.")

    standard_ids = default_option_ids(product)
    snapshot = []
    difference_labels = []
    additional_price = Decimal("0.00")
    for group in groups:
        available_options = [option for option in group.options.all() if option.is_available]
        group_selected = [option for option in available_options if option.pk in selected_ids]
        group_standard = [option for option in available_options if option.is_default]
        selected_pairs = {}
        for option in group_selected:
            pair_key = option.replacement_pair.strip().casefold()
            if pair_key and pair_key in selected_pairs:
                raise ValidationError(
                    f"En {group.name} no puedes elegir {selected_pairs[pair_key].name} y {option.name} al mismo tiempo."
                )
            if pair_key:
                selected_pairs[pair_key] = option
        if group.selection_type == ProductOptionGroup.SelectionType.SINGLE and len(group_selected) > 1:
            raise ValidationError(f"En {group.name} solo puedes elegir una opción.")
        if group.is_required and not group_selected:
            raise ValidationError(f"Elige por lo menos una opción en {group.name}.")
        for option in group_selected:
            additional_price += option.price_adjustment
        removed_options = [option for option in group_standard if option.pk not in selected_ids]
        added_options = [option for option in group_selected if not option.is_default]
        replacements = []
        used_removed_ids = set()
        used_added_ids = set()
        for removed_option in removed_options:
            pair_key = removed_option.replacement_pair.strip().casefold()
            replacement = next(
                (option for option in added_options if pair_key and option.replacement_pair.strip().casefold() == pair_key),
                None,
            )
            if replacement:
                replacements.append(f"Cambiar {removed_option.name} por {replacement.name}")
                used_removed_ids.add(removed_option.pk)
                used_added_ids.add(replacement.pk)
        removed = [option.name for option in removed_options if option.pk not in used_removed_ids]
        added = [option.name for option in added_options if option.pk not in used_added_ids]
        difference_labels.extend(replacements)
        difference_labels.extend(f"Sin {name}" for name in removed)
        difference_labels.extend(f"Agregar {name}" for name in added)
        snapshot.append({
            "group": group.name,
            "selection_type": group.selection_type,
            "selected": [
                {"id": option.pk, "name": option.name, "price_adjustment": str(option.price_adjustment), "replacement_pair": option.replacement_pair}
                for option in group_selected
            ],
            "standard": [option.name for option in group_standard],
        })
    option_signature = ",".join(str(option_id) for option_id in sorted(selected_ids))
    return {
        "option_ids": sorted(selected_ids),
        "signature": f"{option_signature}|comentario:{comment.casefold()}" if comment else option_signature,
        "snapshot": {"groups": snapshot, "differences": difference_labels, "comment": comment},
        "comment": comment,
        "difference_labels": difference_labels,
        "difference_text": " · ".join(difference_labels),
        "is_customized": selected_ids != standard_ids or bool(comment),
        "additional_price": additional_price,
        "unit_price": product.price + additional_price,
    }


def serialize_product_selector(product):
    groups = []
    for group in product.option_groups.all():
        options = [option for option in group.options.all() if option.is_available]
        if not options:
            continue
        groups.append({
            "id": group.pk,
            "name": group.name,
            "selection_type": group.selection_type,
            "is_required": group.is_required,
            "options": [
                {"id": option.pk, "name": option.name, "price_adjustment": str(option.price_adjustment), "is_default": option.is_default, "replacement_pair": option.replacement_pair}
                for option in options
            ],
        })
    return {"id": product.pk, "name": product.name, "base_price": str(product.price), "groups": groups}
