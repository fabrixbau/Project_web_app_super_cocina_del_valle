# NOTA TEMPORAL PARA APRENDIZAJE:
# El navegador envía todos los grupos e ingredientes como JSON. Aquí Django vuelve a validar
# cada dato y sincroniza altas, cambios y eliminaciones conservando IDs existentes. La interfaz
# nunca sustituye esta validación de servidor. Borra esta nota después de leerla.

import json
import uuid
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models

from .models import ProductOption, ProductOptionGroup


MAX_GROUPS = 20
MAX_OPTIONS_PER_GROUP = 50


def serialize_product_customization(product):
    return [serialize_group(group) for group in product.option_groups.all()]


def serialize_group(group, *, as_template=False):
    return {
        "id": None if as_template else group.pk,
        "shared_key": str(group.shared_key),
        "source_label": f"{group.product.name} · {group.name}",
        "name": group.name,
        "selection_type": group.selection_type,
        "is_required": group.is_required,
        "sort_order": group.sort_order,
        "options": [
            {
                "id": None if as_template else option.pk,
                "name": option.name,
                "price_adjustment": str(option.price_adjustment),
                "is_default": option.is_default,
                "is_available": option.is_available,
                "replacement_pair": option.replacement_pair,
                "sort_order": option.sort_order,
            }
            for option in group.options.all()
        ],
    }


def parse_customization_payload(raw_payload):
    try:
        payload = json.loads(raw_payload or "[]")
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError("No fue posible leer los ingredientes. Recarga la pantalla.") from error
    if not isinstance(payload, list) or len(payload) > MAX_GROUPS:
        raise ValidationError(f"Puedes configurar como máximo {MAX_GROUPS} grupos por producto.")

    clean_groups = []
    group_names = set()
    for group_position, raw_group in enumerate(payload, start=1):
        if not isinstance(raw_group, dict):
            raise ValidationError("Uno de los grupos contiene datos inválidos.")
        name = " ".join(str(raw_group.get("name", "")).split())
        if not name or len(name) > 100:
            raise ValidationError(f"El grupo {group_position} necesita un nombre de hasta 100 caracteres.")
        normalized_name = name.casefold()
        if normalized_name in group_names:
            raise ValidationError(f"El grupo {name} está repetido.")
        group_names.add(normalized_name)
        selection_type = raw_group.get("selection_type")
        if selection_type not in ProductOptionGroup.SelectionType.values:
            raise ValidationError(f"Selecciona una forma de elegir válida para {name}.")
        raw_options = raw_group.get("options", [])
        if not isinstance(raw_options, list) or not raw_options:
            raise ValidationError(f"Agrega al menos un ingrediente al grupo {name}.")
        if len(raw_options) > MAX_OPTIONS_PER_GROUP:
            raise ValidationError(f"El grupo {name} supera {MAX_OPTIONS_PER_GROUP} opciones.")

        clean_options = []
        option_names = set()
        pair_default_counts = {}
        pair_counts = {}
        default_count = 0
        for option_position, raw_option in enumerate(raw_options, start=1):
            if not isinstance(raw_option, dict):
                raise ValidationError(f"Una opción del grupo {name} contiene datos inválidos.")
            option_name = " ".join(str(raw_option.get("name", "")).split())
            if not option_name or len(option_name) > 100:
                raise ValidationError(f"La opción {option_position} de {name} necesita un nombre.")
            normalized_option_name = option_name.casefold()
            if normalized_option_name in option_names:
                raise ValidationError(f"La opción {option_name} está repetida dentro de {name}.")
            option_names.add(normalized_option_name)
            try:
                price_adjustment = Decimal(str(raw_option.get("price_adjustment", "0")))
            except (InvalidOperation, TypeError, ValueError) as error:
                raise ValidationError(f"El cargo de {option_name} no es una cantidad válida.") from error
            if price_adjustment < 0 or price_adjustment > Decimal("99999999.99"):
                raise ValidationError(f"El cargo de {option_name} debe ser cero o positivo.")
            is_default = raw_option.get("is_default") is True
            is_available = raw_option.get("is_available") is True
            replacement_pair = " ".join(str(raw_option.get("replacement_pair", "")).split())
            if len(replacement_pair) > 100:
                raise ValidationError(f"El nombre del par de {option_name} supera 100 caracteres.")
            if is_default and not is_available:
                raise ValidationError(f"{option_name} es estándar y debe permanecer disponible.")
            default_count += int(is_default)
            if replacement_pair and is_default:
                normalized_pair = replacement_pair.casefold()
                pair_default_counts[normalized_pair] = pair_default_counts.get(normalized_pair, 0) + 1
            if replacement_pair:
                normalized_pair = replacement_pair.casefold()
                pair_counts[normalized_pair] = pair_counts.get(normalized_pair, 0) + 1
            clean_options.append({
                "id": _optional_positive_id(raw_option.get("id")),
                "name": option_name,
                "price_adjustment": price_adjustment,
                "is_default": is_default,
                "is_available": is_available,
                "replacement_pair": replacement_pair,
                "sort_order": option_position * 10,
            })
        repeated_standard_pair = next((pair for pair, count in pair_default_counts.items() if count > 1), None)
        if repeated_standard_pair:
            raise ValidationError(f"El par {repeated_standard_pair} solo puede tener una opción estándar.")
        incomplete_pair = next((pair for pair, count in pair_counts.items() if count < 2), None)
        if incomplete_pair:
            raise ValidationError(f"El par {incomplete_pair} debe estar escrito en por lo menos dos opciones.")
        if selection_type == ProductOptionGroup.SelectionType.SINGLE and default_count > 1:
            raise ValidationError(f"El grupo {name} solo puede tener una opción estándar.")
        is_required = raw_group.get("is_required") is True
        if is_required and default_count == 0:
            raise ValidationError(f"El grupo obligatorio {name} necesita una opción estándar.")
        clean_groups.append({
            "id": _optional_positive_id(raw_group.get("id")),
            "shared_key": _optional_uuid(raw_group.get("shared_key")),
            "name": name,
            "selection_type": selection_type,
            "is_required": is_required,
            "sort_order": group_position * 10,
            "options": clean_options,
        })
    return clean_groups


def _optional_positive_id(value):
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError("Se recibió un identificador de ingrediente inválido.") from error
    if parsed <= 0:
        raise ValidationError("Se recibió un identificador de ingrediente inválido.")
    return parsed


def _optional_uuid(value):
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError("Se recibió una familia de ingredientes inválida.") from error


def sync_product_customization(product, clean_groups):
    from .group_library import propagate_shared_group
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # Primero reservamos nombres internos para los registros existentes. Esto evita un choque
    # temporal de unicidad cuando un grupo pegado toma el nombre que otro grupo está dejando.
    # Luego se escriben normalmente los nombres finales enviados por el editor. Borra esta nota.
    existing_groups = {
        group.pk: group for group in product.option_groups.prefetch_related("options").all()
    }
    ProductOptionGroup.objects.filter(pk__in=existing_groups).update(name=models.functions.Concat(
        models.Value("__sync_group_"), models.functions.Cast("id", models.CharField()),
    ))
    kept_group_ids = set()
    groups_to_propagate = []
    for group_data in clean_groups:
        group_id = group_data["id"]
        if group_id:
            group = existing_groups.get(group_id)
            if not group:
                raise ValidationError("Uno de los grupos ya no pertenece a este producto.")
            group.name = group_data["name"]
            group.selection_type = group_data["selection_type"]
            group.is_required = group_data["is_required"]
            group.sort_order = group_data["sort_order"]
            group.save(update_fields=("name", "selection_type", "is_required", "sort_order"))
        else:
            group = ProductOptionGroup.objects.create(
                product=product,
                shared_key=group_data["shared_key"] or uuid.uuid4(),
                name=group_data["name"],
                selection_type=group_data["selection_type"],
                is_required=group_data["is_required"],
                sort_order=group_data["sort_order"],
            )
        kept_group_ids.add(group.pk)
        groups_to_propagate.append(group)
        existing_options = {option.pk: option for option in group.options.all()}
        ProductOption.objects.filter(pk__in=existing_options).update(name=models.functions.Concat(
            models.Value("__sync_option_"), models.functions.Cast("id", models.CharField()),
        ))
        kept_option_ids = set()
        for option_data in group_data["options"]:
            option_id = option_data["id"]
            if option_id:
                option = existing_options.get(option_id)
                if not option:
                    raise ValidationError("Una de las opciones ya no pertenece a este grupo.")
                for field in ("name", "price_adjustment", "is_default", "is_available", "replacement_pair", "sort_order"):
                    setattr(option, field, option_data[field])
                option.save(update_fields=("name", "price_adjustment", "is_default", "is_available", "replacement_pair", "sort_order"))
            else:
                option = ProductOption.objects.create(group=group, **{
                    key: option_data[key] for key in (
                        "name", "price_adjustment", "is_default", "is_available", "replacement_pair", "sort_order",
                    )
                })
            kept_option_ids.add(option.pk)
        group.options.exclude(pk__in=kept_option_ids).delete()
    product.option_groups.exclude(pk__in=kept_group_ids).delete()
    for group in groups_to_propagate:
        group.refresh_from_db()
        propagate_shared_group(group)
