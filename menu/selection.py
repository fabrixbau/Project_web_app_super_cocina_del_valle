# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta es la regla compartida por clientes y Mesas. Recibe opciones seleccionadas, comprueba
# que pertenecen al producto y calcula precio, firma, snapshot y diferencias contra la receta
# estándar. Así ambos canales cobran y describen exactamente igual. Borra esta nota.

from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import ProductOptionGroup


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
