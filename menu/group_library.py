# NOTA TEMPORAL PARA APRENDIZAJE:
# Este servicio mantiene sincronizadas las copias técnicas de una misma familia de ingredientes.
# Para el usuario es un solo grupo compartido; cada producto conserva su relación para que los
# selectores existentes sigan funcionando sin cambios. Borra esta nota después de estudiarla.

import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction

from .models import Product, ProductOption, ProductOptionGroup


def shared_group_families():
    groups = ProductOptionGroup.objects.select_related("product").prefetch_related("options").order_by(
        "name", "product__name", "id",
    )
    families = {}
    for group in groups:
        family = families.setdefault(group.shared_key, {"group": group, "products": []})
        family["products"].append(group.product)
    return list(families.values())


@transaction.atomic
def sync_shared_group(clean_group, product_ids, *, shared_key=None):
    target_products = list(Product.objects.filter(pk__in=product_ids).order_by("name"))
    if len(target_products) != len(set(product_ids)) or not target_products:
        raise ValidationError("Selecciona por lo menos un producto válido para el grupo.")
    family_key = shared_key or clean_group.get("shared_key") or uuid.uuid4()
    replicas = {
        group.product_id: group
        for group in ProductOptionGroup.objects.select_for_update().filter(shared_key=family_key).prefetch_related("options")
    }
    target_ids = {product.pk for product in target_products}
    for product in target_products:
        group = replicas.get(product.pk)
        conflicting_name = ProductOptionGroup.objects.filter(
            product=product, name__iexact=clean_group["name"],
        )
        if group:
            conflicting_name = conflicting_name.exclude(pk=group.pk)
        if conflicting_name.exists():
            raise ValidationError(
                f"{product.name} ya tiene otro grupo llamado {clean_group['name']}. "
                "Cámbiale el nombre o desasócialo antes de continuar."
            )
        if group is None:
            group = ProductOptionGroup.objects.create(
                product=product, shared_key=family_key, name=clean_group["name"],
                selection_type=clean_group["selection_type"], is_required=clean_group["is_required"],
                sort_order=clean_group["sort_order"],
            )
        else:
            group.name = clean_group["name"]
            group.selection_type = clean_group["selection_type"]
            group.is_required = clean_group["is_required"]
            group.sort_order = clean_group["sort_order"]
            group.save(update_fields=("name", "selection_type", "is_required", "sort_order"))
        _sync_options(group, clean_group["options"])
    ProductOptionGroup.objects.filter(shared_key=family_key).exclude(product_id__in=target_ids).delete()
    return family_key


def propagate_shared_group(source_group):
    siblings = ProductOptionGroup.objects.filter(shared_key=source_group.shared_key).exclude(pk=source_group.pk)
    source_options = list(source_group.options.all())
    for sibling in siblings:
        if ProductOptionGroup.objects.filter(product=sibling.product, name__iexact=source_group.name).exclude(pk=sibling.pk).exists():
            raise ValidationError(f"{sibling.product.name} ya tiene otro grupo llamado {source_group.name}.")
        sibling.name = source_group.name
        sibling.selection_type = source_group.selection_type
        sibling.is_required = source_group.is_required
        sibling.sort_order = source_group.sort_order
        sibling.save(update_fields=("name", "selection_type", "is_required", "sort_order"))
        sibling.options.all().delete()
        ProductOption.objects.bulk_create([
            ProductOption(
                group=sibling, name=option.name, price_adjustment=option.price_adjustment,
                replacement_pair=option.replacement_pair, is_default=option.is_default,
                is_available=option.is_available, sort_order=option.sort_order,
            )
            for option in source_options
        ])


def _sync_options(group, clean_options):
    existing = list(group.options.all())
    existing_by_id = {option.pk: option for option in existing}
    existing_by_name = {option.name.casefold(): option for option in existing}
    ProductOption.objects.filter(group=group).update(name=models.functions.Concat(
        models.Value("__sync_option_"), models.functions.Cast("id", models.CharField()),
    ))
    kept_ids = set()
    for option_data in clean_options:
        option = existing_by_id.get(option_data["id"]) or existing_by_name.get(option_data["name"].casefold())
        values = {
            key: option_data[key] for key in (
                "name", "price_adjustment", "replacement_pair", "is_default", "is_available", "sort_order",
            )
        }
        if option:
            for key, value in values.items():
                setattr(option, key, value)
            option.save(update_fields=tuple(values))
        else:
            option = ProductOption.objects.create(group=group, **values)
        kept_ids.add(option.pk)
    group.options.exclude(pk__in=kept_ids).delete()
