# NOTA TEMPORAL PARA APRENDIZAJE:
# El cierre bloquea la cuenta, vuelve a sumar consumos y guarda la fotografía del pago.
# Esto evita cerrar dos veces o cobrar con un total desactualizado. Borra esta nota.
# Los paquetes pueden guardarse incompletos y actualizarse después; el cierre los rechaza.
# Comida por orden valida contra los componentes del menú diario publicado antes de vender.
# Al editar un paquete usamos su `daily_menu` original, no el menú de la fecha actual.
# La selección inteligente consume tres órdenes individuales y las sustituye por un paquete.
# Cuando el producto es pollo, la pieza elegida viaja con la orden y con el paquete automático.
# Mesas ignora periodos de servicio: el personal puede seguir capturando después del cierre público.
# Productos y paquetes validan disponibilidad, bloquean la cuenta y recalculan en servidor.
# Estas operaciones sensibles bloquean la mesa o cuenta mientras se modifica. Esto evita
# que dos empleados abran la misma mesa o cambien responsable al mismo tiempo. Borra la nota.
# Productos individuales resuelven opciones con la misma regla pública y se agrupan por firma
# de preparación, no solo por producto. Borra esta nota.

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.roles import WAITER

from menu.models import DailyMenu, MealPackage, Product
from menu.selection import resolve_product_selection

from .models import DiningTable, TableAccount, TableAccountItem, TableActivity


def record_activity(*, account, actor, action, description="", quantity_delta=0, metadata=None):
    return TableActivity.objects.create(account=account, actor=actor, action=action, description=description[:255], quantity_delta=quantity_delta, metadata=metadata or {})


def validate_waiter(user):
    if not user.is_active or not user.groups.filter(name=WAITER).exists():
        raise ValidationError("Selecciona un usuario activo con rol Mesero.")


@transaction.atomic
def open_table_account(*, table, assigned_waiter, opened_by):
    table = DiningTable.objects.select_for_update().get(pk=table.pk)
    if not table.is_active:
        raise ValidationError("Esta mesa está desactivada.")
    if table.accounts.filter(status=TableAccount.Status.OPEN).exists():
        raise ValidationError("La mesa ya tiene una cuenta abierta.")
    validate_waiter(assigned_waiter)
    account = TableAccount.objects.create(
        table=table, assigned_waiter=assigned_waiter, opened_by=opened_by,
    )
    record_activity(account=account, actor=opened_by, action=TableActivity.Action.OPEN, description=f"Responsable: {assigned_waiter.get_full_name() or assigned_waiter.username}")
    return account


@transaction.atomic
def reassign_table_account(*, account, assigned_waiter, changed_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("Solo puedes reasignar una cuenta abierta.")
    validate_waiter(assigned_waiter)
    previous = account.assigned_waiter
    account.assigned_waiter = assigned_waiter
    account.save(update_fields=("assigned_waiter",))
    record_activity(account=account, actor=changed_by, action=TableActivity.Action.REASSIGN, description=f"De {previous.get_full_name() or previous.username} a {assigned_waiter.get_full_name() or assigned_waiter.username}")
    return account


def product_is_available_now(product, *, require_individual=True, enforce_service_period=True):
    if not product.is_available or (require_individual and not product.is_sold_individually):
        return False
    periods = list(product.service_periods.all())
    current_time = timezone.localtime().time()
    return not enforce_service_period or not periods or any(
        period.contains(current_time) for period in periods
    )


def daily_menu_order_product_ids(daily_menu):
    return {
        product_id for product_id in (
            daily_menu.chicken_consomme_id,
            daily_menu.variable_first_course_id,
            daily_menu.second_course_one_id,
            daily_menu.second_course_two_id,
            daily_menu.chicken_stew_id,
            daily_menu.beef_stew_id,
            daily_menu.varied_stew_id,
            daily_menu.beans_order_id,
        ) if product_id
    }


@transaction.atomic
def add_product_to_table(
    *, account, product, added_by, chicken_piece="", is_package_candidate=False,
    require_individual=True, raw_option_ids=None, customization_comment="",
):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya no está abierta.")
    product = Product.objects.select_for_update().prefetch_related(
        "service_periods", "option_groups__options",
    ).get(
        pk=product.pk,
    )
    if not product_is_available_now(
        product,
        require_individual=require_individual and not is_package_candidate,
        enforce_service_period=False,
    ):
        raise ValidationError(f"{product.name} ya no está disponible.")
    selection = resolve_product_selection(product, raw_option_ids, customization_comment)
    item = TableAccountItem.objects.select_for_update().filter(
        account=account, product=product, chicken_piece=chicken_piece,
        is_package_candidate=is_package_candidate,
        configuration_signature=selection["signature"],
    ).order_by("-id").first()
    if item:
        item.quantity += 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    else:
        item = TableAccountItem.objects.create(
            account=account,
            product=product,
            product_name_snapshot=product.name,
            unit_price=selection["unit_price"],
            quantity=1,
            subtotal=selection["unit_price"],
            added_by=added_by,
            chicken_piece=chicken_piece,
            is_package_candidate=is_package_candidate,
            configuration_snapshot=selection["snapshot"],
            configuration_signature=selection["signature"],
            customization_comment=selection["comment"],
            is_customized=selection["is_customized"],
        )
    record_activity(account=account, actor=added_by, action=TableActivity.Action.CUSTOMIZE if selection["is_customized"] else TableActivity.Action.ADD, description=product.name, quantity_delta=1)
    return item


@transaction.atomic
def add_daily_menu_product_to_table(
    *, account, product, daily_menu, added_by, chicken_piece="", raw_option_ids=None,
    customization_comment="",
):
    daily_menu = DailyMenu.objects.select_for_update().get(
        pk=daily_menu.pk, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    if product.pk not in daily_menu_order_product_ids(daily_menu):
        raise ValidationError("Este producto no pertenece al menú diario publicado.")
    if product.pk == daily_menu.chicken_stew_id and chicken_piece not in {"leg", "thigh"}:
        raise ValidationError("Selecciona si la orden de pollo es pierna o muslo.")
    if product.pk != daily_menu.chicken_stew_id:
        chicken_piece = ""
    return add_product_to_table(
        account=account, product=product, added_by=added_by, chicken_piece=chicken_piece,
        require_individual=False, raw_option_ids=raw_option_ids,
        customization_comment=customization_comment,
    )


def consume_product_units(*, account, product_ids, chicken_product_id=None, chicken_piece=""):
    for product_id in product_ids:
        item_queryset = TableAccountItem.objects.select_for_update().filter(
            account=account, product_id=product_id,
            item_type=TableAccountItem.ItemType.PRODUCT,
            is_package_candidate=True,
        )
        if product_id == chicken_product_id:
            item_queryset = item_queryset.filter(chicken_piece=chicken_piece)
        item = item_queryset.order_by("-id").first()
        if not item:
            raise ValidationError("Cambió el ticket y ya no encontramos todos los tiempos seleccionados.")
        if item.quantity == 1:
            item.delete()
        else:
            item.quantity -= 1
            item.subtotal = item.unit_price * item.quantity
            item.save(update_fields=("quantity", "subtotal"))


@transaction.atomic
def add_auto_meal_component(
    *, account, product, daily_menu, completed_selection, added_by, chicken_piece="",
    raw_option_ids=None, customization_comment="",
):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya no está abierta.")
    daily_menu = DailyMenu.objects.select_for_update().get(
        pk=daily_menu.pk, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    product = Product.objects.select_for_update().prefetch_related("service_periods").get(pk=product.pk)
    daily_ids = daily_menu_order_product_ids(daily_menu)
    is_eligible_grill = (
        product.component_type == Product.ComponentType.GRILL
        and product.eligible_for_executive_meal
    )
    if product.pk not in daily_ids and not is_eligible_grill:
        raise ValidationError("Este producto no es elegible para formar una comida del menú de hoy.")
    clicked_chicken_piece = chicken_piece if product.pk == daily_menu.chicken_stew_id else ""
    if product.pk == daily_menu.chicken_stew_id and clicked_chicken_piece not in {"leg", "thigh"}:
        raise ValidationError("Selecciona si el pollo es pierna o muslo.")
    add_product_to_table(
        account=account, product=product, added_by=added_by,
        chicken_piece=clicked_chicken_piece,
        is_package_candidate=True,
        raw_option_ids=raw_option_ids,
        customization_comment=customization_comment,
    )
    if not completed_selection:
        return None

    selected_products = Product.objects.select_for_update().in_bulk(
        completed_selection[key] for key in ("first", "second", "main")
    )
    try:
        first = selected_products[completed_selection["first"]]
        second = selected_products[completed_selection["second"]]
        main = selected_products[completed_selection["main"]]
    except KeyError as error:
        raise ValidationError("No encontramos uno de los tiempos seleccionados.") from error
    if first.pk not in {daily_menu.chicken_consomme_id, daily_menu.variable_first_course_id}:
        raise ValidationError("El primer tiempo ya no pertenece al menú diario.")
    if second.pk not in {daily_menu.second_course_one_id, daily_menu.second_course_two_id}:
        raise ValidationError("El segundo tiempo ya no pertenece al menú diario.")
    if main.component_type == Product.ComponentType.GRILL and main.eligible_for_executive_meal:
        package_type = MealPackage.PackageType.EXECUTIVE
    elif main.pk in {
        product_id for product_id in (
            daily_menu.chicken_stew_id, daily_menu.beef_stew_id, daily_menu.varied_stew_id,
        ) if product_id
    }:
        package_type = MealPackage.PackageType.RUNNING
    else:
        raise ValidationError("El tercer tiempo no puede completar un paquete.")
    if main.pk == daily_menu.chicken_stew_id and chicken_piece not in {"leg", "thigh"}:
        raise ValidationError("No encontramos la pieza elegida para el pollo.")
    if main.pk != daily_menu.chicken_stew_id:
        chicken_piece = ""
    package = MealPackage.objects.select_for_update().filter(
        package_type=package_type, is_active=True,
    ).order_by("id").first()
    if not package:
        raise ValidationError("No existe un paquete activo para completar esta comida.")
    component_comments = []
    for selected_product in (first, second, main):
        candidate = TableAccountItem.objects.filter(
            account=account, product=selected_product,
            item_type=TableAccountItem.ItemType.PRODUCT, is_package_candidate=True,
        ).exclude(customization_comment="").order_by("-id").first()
        if candidate:
            component_comments.append(
                f"{candidate.product_name_snapshot}: {candidate.customization_comment}"
            )
    package_comment = " · ".join(component_comments)
    consume_product_units(
        account=account,
        product_ids=(first.pk, second.pk, main.pk),
        chicken_product_id=daily_menu.chicken_stew_id,
        chicken_piece=chicken_piece,
    )
    cleaned_data = {
        "first_course": first,
        "second_course": second,
        "main_course": main,
        "chicken_piece": chicken_piece,
        "with_water": False,
        "refill_extra": False,
        "is_complete": True,
        "customization_comment": package_comment,
        "configuration_signature": f"comentarios:{package_comment.casefold()}" if package_comment else "",
        "configuration_snapshot": {"differences": component_comments, "comment": package_comment},
        "is_customized": bool(package_comment),
    }
    return add_package_to_table(
        account=account, package=package, daily_menu=daily_menu,
        cleaned_data=cleaned_data, added_by=added_by,
    )


@transaction.atomic
def add_package_to_table(*, account, package, daily_menu, cleaned_data, added_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya no está abierta.")
    package = MealPackage.objects.select_for_update().get(pk=package.pk, is_active=True)
    daily_menu = DailyMenu.objects.select_for_update().get(
        pk=daily_menu.pk, date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    )
    first = cleaned_data.get("first_course")
    second = cleaned_data.get("second_course")
    main = cleaned_data.get("main_course")
    price = package.price_with_water if cleaned_data["with_water"] else package.price_without_water
    if cleaned_data["refill_extra"]:
        price += package.table_refill_price
    signature = {
        "account": account, "item_type": TableAccountItem.ItemType.PACKAGE,
        "package": package, "daily_menu": daily_menu,
        "first_course_product": first, "first_course_snapshot": first.name if first else "",
        "second_course_product": second, "second_course_snapshot": second.name if second else "",
        "main_course_product": main, "main_course_snapshot": main.name if main else "",
        "chicken_piece": cleaned_data["chicken_piece"],
        "with_water": cleaned_data["with_water"],
        "tortillas": False, "beans": False,
        "refill_extra": cleaned_data["refill_extra"],
        "is_complete": cleaned_data["is_complete"],
        "customization_comment": cleaned_data.get("customization_comment", ""),
        "configuration_signature": cleaned_data.get("configuration_signature", ""),
        "configuration_snapshot": cleaned_data.get("configuration_snapshot", {}),
        "is_customized": cleaned_data.get("is_customized", False),
    }
    item = TableAccountItem.objects.select_for_update().filter(**signature).order_by("-id").first()
    if item:
        item.quantity += 1
        item.subtotal = item.unit_price * item.quantity
        item.save(update_fields=("quantity", "subtotal"))
    else:
        item = TableAccountItem.objects.create(
            **signature, product_name_snapshot=package.name,
            package_name_snapshot=package.name,
            water_name_snapshot=daily_menu.water_product.name if cleaned_data["with_water"] else "",
            unit_price=price, quantity=1, subtotal=price, added_by=added_by,
        )
    record_activity(account=account, actor=added_by, action=TableActivity.Action.PACKAGE, description=package.name, quantity_delta=1)
    return item


@transaction.atomic
def update_table_package(*, account, item, package, daily_menu, cleaned_data, changed_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya no está abierta.")
    item = TableAccountItem.objects.select_for_update().get(
        pk=item.pk, account=account, item_type=TableAccountItem.ItemType.PACKAGE,
    )
    package = MealPackage.objects.select_for_update().get(pk=package.pk)
    daily_menu = DailyMenu.objects.select_for_update().get(pk=daily_menu.pk)
    if item.package_id != package.pk:
        raise ValidationError("La partida no corresponde a este paquete.")
    if item.daily_menu_id and item.daily_menu_id != daily_menu.pk:
        raise ValidationError("La partida no corresponde a este menú diario.")
    if not item.daily_menu_id:
        item.daily_menu = daily_menu
    first = cleaned_data.get("first_course")
    second = cleaned_data.get("second_course")
    main = cleaned_data.get("main_course")
    price = package.price_with_water if cleaned_data["with_water"] else package.price_without_water
    if cleaned_data["refill_extra"]:
        price += package.table_refill_price
    item.first_course_product = first
    item.first_course_snapshot = first.name if first else ""
    item.second_course_product = second
    item.second_course_snapshot = second.name if second else ""
    item.main_course_product = main
    item.main_course_snapshot = main.name if main else ""
    item.chicken_piece = cleaned_data["chicken_piece"]
    item.with_water = cleaned_data["with_water"]
    item.water_name_snapshot = daily_menu.water_product.name if cleaned_data["with_water"] else ""
    item.refill_extra = cleaned_data["refill_extra"]
    item.tortillas = False
    item.beans = False
    item.is_complete = cleaned_data["is_complete"]
    item.customization_comment = cleaned_data.get("customization_comment", "")
    item.configuration_signature = cleaned_data.get("configuration_signature", "")
    item.configuration_snapshot = cleaned_data.get("configuration_snapshot", {})
    item.is_customized = cleaned_data.get("is_customized", False)
    item.unit_price = price
    item.subtotal = price * item.quantity
    item.save(update_fields=(
        "first_course_product", "first_course_snapshot", "second_course_product",
        "second_course_snapshot", "main_course_product", "main_course_snapshot",
        "chicken_piece", "with_water", "water_name_snapshot", "refill_extra", "tortillas", "beans",
        "daily_menu", "is_complete", "customization_comment", "configuration_signature",
        "configuration_snapshot", "is_customized", "unit_price", "subtotal",
    ))
    record_activity(account=account, actor=changed_by, action=TableActivity.Action.PACKAGE_EDIT, description=package.name)
    return item


@transaction.atomic
def change_item_in_ticket(*, account, item, action, changed_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya no está abierta.")
    item = TableAccountItem.objects.select_for_update().get(pk=item.pk, account=account)
    item_query = TableAccountItem.objects.filter(pk=item.pk)
    if item.item_type == TableAccountItem.ItemType.PRODUCT and item.product_id:
        item_query = TableAccountItem.objects.filter(
            account=account, product_id=item.product_id, chicken_piece=item.chicken_piece,
            is_package_candidate=item.is_package_candidate,
            configuration_signature=item.configuration_signature,
        )
    items = list(item_query.select_for_update().order_by("-id"))
    if not items:
        raise ValidationError("El producto ya no está en el ticket.")
    description = item.product_name_snapshot
    if action == "remove":
        removed_quantity = sum(candidate.quantity for candidate in items)
        TableAccountItem.objects.filter(pk__in=[item.pk for item in items]).delete()
        record_activity(account=account, actor=changed_by, action=TableActivity.Action.REMOVE, description=description, quantity_delta=-removed_quantity)
        return
    item = items[0]
    if action == "increase":
        item.quantity += 1
    elif action == "decrease":
        if item.quantity > 1:
            item.quantity -= 1
        else:
            item.delete()
            record_activity(account=account, actor=changed_by, action=TableActivity.Action.DECREASE, description=description, quantity_delta=-1)
            return
    else:
        raise ValidationError("La acción solicitada no es válida.")
    item.subtotal = item.unit_price * item.quantity
    item.save(update_fields=("quantity", "subtotal"))
    event = TableActivity.Action.INCREASE if action == "increase" else TableActivity.Action.DECREASE
    record_activity(account=account, actor=changed_by, action=event, description=description, quantity_delta=1 if action == "increase" else -1)


@transaction.atomic
def close_table_account(*, account, cleaned_data, closed_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya fue cerrada.")
    items = list(account.items.select_for_update().only(
        "subtotal", "item_type", "is_complete", "is_package_candidate", "product_name_snapshot",
    ))
    if not items:
        raise ValidationError("No puedes cerrar una cuenta sin consumos.")
    incomplete_items = [
        item.product_name_snapshot for item in items
        if item.item_type == TableAccountItem.ItemType.PACKAGE and not item.is_complete
    ]
    if incomplete_items:
        pending_names = ", ".join(incomplete_items)
        raise ValidationError(
            "No se puede cerrar la cuenta porque hay comidas incompletas: "
            f"{pending_names}. Completa los tiempos pendientes antes de continuar."
        )
    pending_components = [
        item.product_name_snapshot for item in items
        if item.item_type == TableAccountItem.ItemType.PRODUCT and item.is_package_candidate
    ]
    if pending_components:
        raise ValidationError(
            "No se puede cerrar la cuenta porque hay selecciones de paquete pendientes: "
            f"{', '.join(pending_components)}. Completa el paquete o elimina esas partidas."
        )
    subtotal = sum((item.subtotal for item in items), start=Decimal("0"))
    tip = cleaned_data["tip_amount"]
    total = subtotal + tip
    method = cleaned_data["payment_method"]
    cash_tendered = cleaned_data.get("cash_tendered")
    if method == TableAccount.PaymentMethod.CASH:
        if cash_tendered is None or cash_tendered < total:
            raise ValidationError("El efectivo recibido no cubre el total actualizado.")
        change = cash_tendered - total
    else:
        cash_tendered = None
        change = None
    account.status = TableAccount.Status.CLOSED
    account.closed_at = timezone.now()
    account.closed_by = closed_by
    account.payment_method = method
    account.subtotal_closed = subtotal
    account.tip_amount = tip
    account.tip_recipient = account.assigned_waiter
    account.total_paid = total
    account.cash_tendered = cash_tendered
    account.change_given = change
    account.save(update_fields=(
        "status", "closed_at", "closed_by", "payment_method", "subtotal_closed",
        "tip_amount", "tip_recipient", "total_paid", "cash_tendered", "change_given",
    ))
    record_activity(account=account, actor=closed_by, action=TableActivity.Action.CLOSE, description=f"{account.get_payment_method_display()} · ${total}", metadata={"tip": str(tip), "responsible_waiter_id": account.assigned_waiter_id})
    return account
