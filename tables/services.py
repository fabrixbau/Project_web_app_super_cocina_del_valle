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

from menu.inventory import release_stock, reserve_stock
from menu.models import DailyMenu, DailyProductStock, MealPackage, Product, StockMovement
from menu.packaging import selected_packaging_products
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
    # NOTA TEMPORAL PARA APRENDIZAJE: ya no se limita a cuentas abiertas. Si la cuenta
    # está cerrada, `tip_recipient` (usado en reportes de propinas) y el `TerminalMovement`
    # ya vinculado a esta mesa (si lo hay) se actualizan también, para que la conciliación
    # de terminales y el reporte de propinas queden coherentes con el nuevo responsable en
    # vez de seguir mostrando a quien ya no lo es. Borra esta nota después de leerla.
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    validate_waiter(assigned_waiter)
    previous = account.assigned_waiter
    account.assigned_waiter = assigned_waiter
    update_fields = ["assigned_waiter"]
    if account.status == TableAccount.Status.CLOSED:
        account.tip_recipient = assigned_waiter
        update_fields.append("tip_recipient")
    account.save(update_fields=update_fields)
    if account.status == TableAccount.Status.CLOSED:
        account.terminal_movements.update(tip_recipient=assigned_waiter)
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


def _stock_for(*, product=None, item_kind=DailyProductStock.ItemKind.PRODUCT, date, required=False, chicken_piece=""):
    filters = {
        "date": date, "channel": DailyProductStock.Channel.TABLE,
        "stock_type": DailyProductStock.StockType.DAILY,
        "item_kind": item_kind, "chicken_piece": chicken_piece,
    }
    filters["product"] = product if product else None
    stock = (
        DailyProductStock.objects.select_for_update()
        .filter(**filters)
        .order_by("pk")
        .first()
    )
    if not stock and chicken_piece:
        stock = (
            DailyProductStock.objects.select_for_update()
            .filter(**{**filters, "chicken_piece": ""})
            .order_by("pk")
            .first()
        )
    if not stock and product and not required:
        stock = (
            DailyProductStock.objects.select_for_update()
            .filter(
                stock_type=DailyProductStock.StockType.FIXED,
                product=product,
                channel=DailyProductStock.Channel.SHARED,
                is_tracked=True,
            )
            .order_by("pk")
            .first()
        )
    if required and not stock:
        name = product.name if product else dict(DailyProductStock.ItemKind.choices)[item_kind]
        raise ValidationError(f"{name} no tiene raciones configuradas para mesas.")
    return stock


def _change_item_stock(*, item, quantity, actor, reserve):
    """Reserve/release all components represented by `quantity` units of one ticket row."""
    if not quantity:
        return
    menu = item.daily_menu
    stock_date = menu.date if menu else timezone.localdate()
    requirements = []
    if item.item_type == TableAccountItem.ItemType.PACKAGE:
        requirements.extend(product for product in (
            item.first_course_product, item.second_course_product, item.main_course_product,
            (item.water_product or (menu.water_product if menu else None)) if item.with_water else None,
            (item.beans_product or (menu.beans_order if menu else None)) if item.beans else None,
            item.egg_product,
        ) if product)
        if item.tortillas:
            requirements.append(DailyProductStock.ItemKind.TORTILLAS)
        if item.bread:
            requirements.append(DailyProductStock.ItemKind.BREAD)
    elif item.product_id:
        requirements.append(DailyProductStock.ItemKind.BREAD if item.product.uses_bread_stock else item.product)

    for requirement in requirements:
        is_product = isinstance(requirement, Product)
        is_required_daily_product = bool(
            menu and is_product and requirement.pk in daily_menu_order_product_ids(menu)
        ) or bool(menu and is_product and requirement.pk == menu.water_product_id)
        stock = _stock_for(
            product=requirement if is_product else None,
            item_kind=DailyProductStock.ItemKind.PRODUCT if is_product else requirement,
            date=stock_date,
            required=bool(not is_product and requirement == DailyProductStock.ItemKind.BREAD) or bool(menu and not is_product) or is_required_daily_product,
            chicken_piece=(
                item.chicken_piece
                if is_product and menu and requirement.pk == menu.chicken_stew_id
                else ""
            ),
        )
        if not stock:
            continue
        operation = reserve_stock if reserve else release_stock
        operation(
            stock=stock, quantity=quantity, actor=actor,
            reference_type="table_item", reference_id=item.pk,
            note=f"{item.account.table.name}: {item.product_name_snapshot}",
        )


@transaction.atomic
def add_product_to_table(
    *, account, product, added_by, chicken_piece="", is_package_candidate=False,
    require_individual=True, raw_option_ids=None, customization_comment="", daily_menu=None,
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
        daily_menu=daily_menu,
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
            daily_menu=daily_menu,
            configuration_snapshot=selection["snapshot"],
            configuration_signature=selection["signature"],
            customization_comment=selection["comment"],
            is_customized=selection["is_customized"],
        )
    _change_item_stock(item=item, quantity=1, actor=added_by, reserve=True)
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
        customization_comment=customization_comment, daily_menu=daily_menu,
    )


def consume_product_units(*, account, product_ids, actor, chicken_product_id=None, chicken_piece=""):
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
        _change_item_stock(item=item, quantity=1, actor=actor, reserve=False)
        if item.quantity == 1:
            item.delete()
        else:
            item.quantity -= 1
            item.subtotal = item.unit_price * item.quantity
            item.save(update_fields=("quantity", "subtotal"))


@transaction.atomic
def add_auto_meal_component(
    *, account, product, daily_menu, completed_selection, added_by, chicken_piece="",
    raw_option_ids=None, customization_comment="", egg_product=None,
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
        daily_menu=daily_menu,
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
    customization_surcharge = Decimal("0")
    for selected_product in (first, second, main):
        candidate = TableAccountItem.objects.filter(
            account=account, product=selected_product,
            item_type=TableAccountItem.ItemType.PRODUCT, is_package_candidate=True,
        ).order_by("-id").first()
        if candidate:
            customization_surcharge += max(candidate.unit_price - selected_product.price, Decimal("0"))
            if candidate.customization_comment:
                component_comments.append(
                    f"{candidate.product_name_snapshot}: {candidate.customization_comment}"
                )
    package_comment = " · ".join(component_comments)
    consume_product_units(
        account=account,
        product_ids=(first.pk, second.pk, main.pk),
        actor=added_by,
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
        "configuration_signature": (
            f"comentarios:{package_comment.casefold()}|extra:{customization_surcharge}"
            if package_comment or customization_surcharge else ""
        ),
        "configuration_snapshot": {
            "differences": component_comments,
            "comment": package_comment,
            "price_delta": str(customization_surcharge),
        },
        "is_customized": bool(package_comment or customization_surcharge),
        "customization_surcharge": customization_surcharge,
        "egg_product": egg_product,
    }
    return add_package_to_table(
        account=account, package=package, daily_menu=daily_menu,
        cleaned_data=cleaned_data, added_by=added_by,
    )


@transaction.atomic
def add_package_to_table(
    *, account, package, daily_menu, cleaned_data, added_by,
    packaging_quantities=None,
):
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
    egg = cleaned_data.get("egg_product")
    price = (
        (package.price_with_water if cleaned_data["with_water"] else package.price_without_water)
        + (egg.price if egg else Decimal("0"))
        + cleaned_data.get("customization_surcharge", Decimal("0"))
    )
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
        "tortillas": False, "bread": cleaned_data.get("bread", False), "beans": False,
        "refill_extra": cleaned_data["refill_extra"],
        "egg_product": egg, "egg_name_snapshot": egg.name if egg else "", "egg_price_snapshot": egg.price if egg else Decimal("0"),
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
            water_product=daily_menu.water_product if cleaned_data["with_water"] else None,
            beans_product=daily_menu.beans_order if cleaned_data.get("beans") else None,
            unit_price=price, quantity=1, subtotal=price, added_by=added_by,
        )
    _change_item_stock(item=item, quantity=1, actor=added_by, reserve=True)
    record_activity(account=account, actor=added_by, action=TableActivity.Action.PACKAGE, description=package.name, quantity_delta=1)
    # NOTA TEMPORAL PARA APRENDIZAJE: los envases siguen siendo partidas separadas;
    # este bloque sólo garantiza que comida y cargos se guarden juntos o ninguno se
    # guarde si un envase dejó de estar disponible. Borra esta nota después de leerla.
    for packaging_product, quantity in selected_packaging_products(packaging_quantities or {}):
        for _ in range(quantity):
            add_product_to_table(
                account=account, product=packaging_product, added_by=added_by,
            )
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
    _change_item_stock(item=item, quantity=item.quantity, actor=changed_by, reserve=False)
    first = cleaned_data.get("first_course")
    second = cleaned_data.get("second_course")
    main = cleaned_data.get("main_course")
    egg = cleaned_data.get("egg_product")
    egg_price = (item.egg_price_snapshot if egg and item.egg_product_id == egg.pk else egg.price) if egg else Decimal("0")
    price = (package.price_with_water if cleaned_data["with_water"] else package.price_without_water) + egg_price
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
    item.water_product = daily_menu.water_product if cleaned_data["with_water"] else None
    item.refill_extra = cleaned_data["refill_extra"]
    item.tortillas = False
    item.bread = cleaned_data.get("bread", False)
    item.beans = False
    item.beans_product = None
    item.egg_product = egg
    item.egg_name_snapshot = egg.name if egg else ""
    item.egg_price_snapshot = egg_price
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
        "chicken_piece", "with_water", "water_name_snapshot", "water_product", "refill_extra", "tortillas", "bread", "beans", "beans_product",
        "daily_menu", "is_complete", "customization_comment", "configuration_signature",
        "egg_product", "egg_name_snapshot", "egg_price_snapshot",
        "configuration_snapshot", "is_customized", "unit_price", "subtotal",
    ))
    _change_item_stock(item=item, quantity=item.quantity, actor=changed_by, reserve=True)
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
            daily_menu_id=item.daily_menu_id,
            configuration_signature=item.configuration_signature,
        )
    items = list(item_query.select_for_update().order_by("-id"))
    if not items:
        raise ValidationError("El producto ya no está en el ticket.")
    description = item.product_name_snapshot
    if action == "remove":
        removed_quantity = sum(candidate.quantity for candidate in items)
        for candidate in items:
            _change_item_stock(
                item=candidate, quantity=candidate.quantity, actor=changed_by, reserve=False,
            )
        TableAccountItem.objects.filter(pk__in=[item.pk for item in items]).delete()
        record_activity(account=account, actor=changed_by, action=TableActivity.Action.REMOVE, description=description, quantity_delta=-removed_quantity)
        return
    item = items[0]
    if action == "increase":
        _change_item_stock(item=item, quantity=1, actor=changed_by, reserve=True)
        item.quantity += 1
    elif action == "decrease":
        _change_item_stock(item=item, quantity=1, actor=changed_by, reserve=False)
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


def _validate_items_closeable(items, *, allow_empty=False):
    # NOTA TEMPORAL PARA APRENDIZAJE: esta validación se comparte entre el cierre normal
    # (todos los artículos de la cuenta) y cada cuenta dividida (sólo sus artículos
    # asignados) — ambas necesitan la misma regla de "nada incompleto ni pendiente".
    # Borra esta nota después de leerla.
    if not items and not allow_empty:
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


def _finalize_account_close(*, account, items, payment_method, tip_amount, cash_tendered, responsible_waiter, closed_by):
    # NOTA TEMPORAL PARA APRENDIZAJE: hace el cierre real de UNA cuenta (la normal, o una
    # de las varias en que se dividió la mesa) ya con sus artículos decididos. No
    # selecciona ni valida artículos por sí sola — eso lo hace quien la llama, porque en
    # una división cada cuenta sólo ve el subconjunto que le tocó. Borra esta nota.
    _validate_items_closeable(items)
    subtotal = sum((item.subtotal for item in items), start=Decimal("0"))
    total = subtotal + tip_amount
    if payment_method == TableAccount.PaymentMethod.CASH:
        if cash_tendered is None or cash_tendered < total:
            raise ValidationError("El efectivo recibido no cubre el total actualizado.")
        change = cash_tendered - total
    else:
        cash_tendered = None
        change = None
    validate_waiter(responsible_waiter)
    account.status = TableAccount.Status.CLOSED
    account.closed_at = timezone.now()
    account.closed_by = closed_by
    account.payment_method = payment_method
    account.subtotal_closed = subtotal
    account.tip_amount = tip_amount
    # NOTA TEMPORAL PARA APRENDIZAJE: antes `tip_recipient` se copiaba en automático de
    # `assigned_waiter` (quien fuera que abrió la mesa o la tuviera asignada por el login),
    # sin confirmarlo. Ahora quien cierra debe elegir explícitamente a quién se queda la
    # mesa, y esa elección actualiza tanto el responsable como quien recibe la propina.
    # Borra esta nota después de leerla.
    account.assigned_waiter = responsible_waiter
    account.tip_recipient = responsible_waiter
    account.total_paid = total
    account.cash_tendered = cash_tendered
    account.change_given = change
    account.save(update_fields=(
        "status", "closed_at", "closed_by", "payment_method", "subtotal_closed",
        "tip_amount", "assigned_waiter", "tip_recipient", "total_paid", "cash_tendered", "change_given",
    ))
    StockMovement.objects.filter(
        reference_type="table_item",
        reference_id__in=[item.pk for item in items],
        reason=StockMovement.Reason.RESERVATION,
    ).update(reason=StockMovement.Reason.CONSUMPTION)
    record_activity(account=account, actor=closed_by, action=TableActivity.Action.CLOSE, description=f"{account.get_payment_method_display()} · ${total}", metadata={"tip": str(tip_amount), "responsible_waiter_id": account.assigned_waiter_id})
    return account


@transaction.atomic
def close_table_account(*, account, cleaned_data, closed_by):
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya fue cerrada.")
    items = list(account.items.select_for_update().only(
        "subtotal", "item_type", "is_complete", "is_package_candidate", "product_name_snapshot",
    ))
    return _finalize_account_close(
        account=account, items=items,
        payment_method=cleaned_data["payment_method"], tip_amount=cleaned_data["tip_amount"],
        cash_tendered=cleaned_data.get("cash_tendered"), responsible_waiter=cleaned_data["responsible_waiter"],
        closed_by=closed_by,
    )


@transaction.atomic
def split_and_close_table_account(*, account, splits, responsible_waiter, closed_by):
    # NOTA TEMPORAL PARA APRENDIZAJE: `splits` es una lista de dicts ya validados por la
    # vista: [{"item_quantities": {item_pk: cantidad, ...}, "payment_method": ...,
    # "tip_amount": ..., "cash_tendered": ...}, ...]. La primera cuenta reutiliza la
    # cuenta ya abierta; el resto se crea como cuentas nuevas de la misma mesa. Un solo
    # mesero se acredita en todas (así se confirmó con el desarrollador) — sólo cambian
    # método de pago, propina y efectivo por cuenta. Todo o nada: si una sola división
    # falla su validación, ninguna se cierra. Borra esta nota después de leerla.
    #
    # NOTA TEMPORAL PARA APRENDIZAJE: un mismo artículo (mismo pk) puede repartirse en
    # varias cuentas divididas cuando su `quantity` es mayor a 1 (dos comidas idénticas
    # agrupadas en una sola partida) — antes esto era imposible porque sólo se podía
    # mover la partida completa. Se permite ahora siempre que la suma de cantidades
    # asignadas a ese pk, en todas las divisiones, coincida exactamente con su
    # `quantity` real. Cuando una división se queda con menos que el total, esa porción
    # se separa en una partida nueva (mismos datos, cantidad y subtotal recalculado); la
    # partida original se reduce y termina asignándose completa a la última división que
    # la usa, evitando crear una fila nueva quando no hace falta. Los movimientos de
    # inventario (`StockMovement`) de esa partida original se consumen todos juntos con
    # la primera división que se cierre — no se reparten entre las partidas nuevas; el
    # total de inventario sigue siendo correcto, sólo la atribución de cuál cuenta
    # disparó el consumo puede no ser exacta para las porciones separadas. Borra esta
    # nota después de leerla.
    account = TableAccount.objects.select_for_update().get(pk=account.pk)
    if account.status != TableAccount.Status.OPEN:
        raise ValidationError("La cuenta ya fue cerrada.")
    if len(splits) < 2:
        raise ValidationError("Divide la cuenta en al menos dos partes.")
    all_items = list(account.items.select_for_update().all())
    _validate_items_closeable(all_items)
    items_by_id = {item.pk: item for item in all_items}
    assigned_quantity = {}
    item_portions = {item.pk: [] for item in all_items}
    for index, split in enumerate(splits):
        for item_pk, quantity in split["item_quantities"].items():
            if item_pk not in items_by_id:
                raise ValidationError("Alguno de los artículos ya no pertenece a esta cuenta.")
            if quantity < 1:
                raise ValidationError("La cantidad asignada debe ser mayor a cero.")
            assigned_quantity[item_pk] = assigned_quantity.get(item_pk, 0) + quantity
            item_portions[item_pk].append((index, quantity))
    for item in all_items:
        if assigned_quantity.get(item.pk, 0) != item.quantity:
            raise ValidationError("Todos los artículos del ticket deben quedar asignados a alguna cuenta antes de dividir.")
    validate_waiter(responsible_waiter)

    # NOTA TEMPORAL PARA APRENDIZAJE: una mesa sólo puede tener UNA cuenta abierta a la
    # vez (`unique_open_account_per_table`), así que las cuentas nuevas no pueden
    # crearse todas por adelantado — cada una se crea, recibe sus artículos y se cierra
    # antes de crear la siguiente, igual que hacía la versión anterior de esta función.
    # Borra esta nota después de leerla.
    last_split_index_for_item = {
        item_pk: max(index for index, _ in portions) for item_pk, portions in item_portions.items()
    }
    remaining_by_item = dict(items_by_id)
    closed_accounts = []
    for index, split in enumerate(splits):
        target_account = account if index == 0 else TableAccount.objects.create(
            table=account.table, assigned_waiter=responsible_waiter, opened_by=account.opened_by,
        )
        if index > 0:
            record_activity(
                account=target_account, actor=closed_by, action=TableActivity.Action.OPEN,
                description=f"Cuenta dividida de {account.table.name}",
            )
        split_items = []
        for item_pk, quantity in split["item_quantities"].items():
            remaining = remaining_by_item[item_pk]
            if index == last_split_index_for_item[item_pk]:
                if remaining.account_id != target_account.pk:
                    remaining.account = target_account
                    remaining.save(update_fields=["account"])
                split_items.append(remaining)
            else:
                new_item = TableAccountItem.objects.get(pk=remaining.pk)
                new_item.pk = None
                new_item.id = None
                new_item._state.adding = True
                new_item.account = target_account
                new_item.quantity = quantity
                new_item.subtotal = new_item.unit_price * quantity
                new_item.save(force_insert=True)
                split_items.append(new_item)
                remaining.quantity -= quantity
                remaining.subtotal = remaining.unit_price * remaining.quantity
                remaining.save(update_fields=["quantity", "subtotal"])
        closed_accounts.append(_finalize_account_close(
            account=target_account, items=split_items,
            payment_method=split["payment_method"], tip_amount=split["tip_amount"],
            cash_tendered=split.get("cash_tendered"), responsible_waiter=responsible_waiter,
            closed_by=closed_by,
        ))
    return closed_accounts
