from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.roles import DELIVERY, ORDER_TAKER, WAITER

from .catalog import limit_cold_drinks_to_daily_water
from .forms import DailyMenuForm
from .inventory import adjust_stock, release_stock, reserve_stock, transfer_stock
from .models import Category, DailyProductStock, InventoryAuditLog, Product, StockMovement


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ProductImageFramingTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="image_framing_admin", password="test-password",
        )
        self.client.force_login(self.admin)
        self.category = Category.objects.create(name="Productos con imagen")
        image_bytes = BytesIO()
        Image.new("RGB", (800, 600), "#d08343").save(image_bytes, format="JPEG")
        self.product = Product.objects.create(
            category=self.category,
            name="Producto encuadrable",
            price=Decimal("75.00"),
            image=SimpleUploadedFile(
                "producto.jpg", image_bytes.getvalue(), content_type="image/jpeg",
            ),
        )

    def test_product_edit_persists_image_framing_without_replacing_image(self):
        original_image_name = self.product.image.name
        response = self.client.post(
            reverse("menu:product_edit", args=(self.product.pk,)),
            {
                "category": self.category.pk,
                "name": self.product.name,
                "price": "75.00",
                "description": "",
                "image_position_x": "18",
                "image_position_y": "82",
                "image_zoom": "2.25",
                "is_available": "on",
                "show_to_customers": "yes",
                "component_type": Product.ComponentType.GENERAL,
                "is_sold_individually": "on",
                "packaging_kind": Product.PackagingKind.NONE,
                "sort_order": "0",
                "customization_data": "[]",
            },
        )

        self.assertRedirects(response, reverse("menu:configuration"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.image_position_x, 18)
        self.assertEqual(self.product.image_position_y, 82)
        self.assertEqual(self.product.image_zoom, Decimal("2.25"))
        self.assertEqual(self.product.image.name, original_image_name)

    def test_generated_card_image_is_never_served_from_stale_browser_cache(self):
        response = self.client.get(
            reverse("menu:product_card_image", args=(self.product.pk,)),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store, max-age=0")
        self.assertEqual(response.headers["Pragma"], "no-cache")


class DailyMenuFormDefaultsTests(TestCase):
    def test_product_selectors_use_touch_toggle_and_portions_start_at_zero(self):
        form = DailyMenuForm()

        for field_name in DailyMenuForm.STOCK_FIELDS:
            self.assertIn("data-click-toggle-select", form.fields[field_name].widget.attrs)

        quantity_fields = [
            field for name, field in form.fields.items()
            if name.startswith("stock_")
        ]
        self.assertTrue(quantity_fields)
        self.assertTrue(all(field.initial == 0 for field in quantity_fields))


class DailyWaterCatalogTests(SimpleTestCase):
    def test_keeps_permanent_drinks_and_only_selected_daily_water(self):
        orange_juice = SimpleNamespace(pk=1, component_type="beverage", is_available=True)
        jamaica = SimpleNamespace(pk=2, component_type="daily_water", is_available=True)
        horchata = SimpleNamespace(pk=3, component_type="daily_water", is_available=True)
        category = SimpleNamespace(
            name="Bebidas frías",
            available_products=[orange_juice, jamaica, horchata],
        )
        daily_menu = SimpleNamespace(water_product_id=jamaica.pk)

        result = limit_cold_drinks_to_daily_water(
            [category], daily_menu, "available_products",
        )

        self.assertEqual(result, [category])
        self.assertEqual(category.available_products, [orange_juice, jamaica])

    def test_does_not_filter_catalog_without_published_daily_menu(self):
        products = [SimpleNamespace(pk=1, component_type="daily_water", is_available=True)]
        category = SimpleNamespace(name="Bebidas frías", available_products=products)

        result = limit_cold_drinks_to_daily_water(
            [category], None, "available_products",
        )

        self.assertEqual(result, [category])
        self.assertEqual(category.available_products, products)


class DailyStockLedgerTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="inventory_manager", password="test-password",
        )
        category = Category.objects.create(name="Comida por orden")
        self.product = Product.objects.create(
            category=category, name="Hamburguesa", price=80,
        )
        self.table_stock = DailyProductStock.objects.create(
            product=self.product,
            channel=DailyProductStock.Channel.TABLE,
            initial_quantity=10,
        )
        self.delivery_stock = DailyProductStock.objects.create(
            product=self.product,
            channel=DailyProductStock.Channel.ORDERS,
            initial_quantity=4,
        )

    def test_reservation_updates_only_its_channel_and_keeps_reference(self):
        movement = reserve_stock(
            stock=self.table_stock,
            quantity=3,
            actor=self.actor,
            reference_type="table_account",
            reference_id=71,
        )

        self.assertEqual(self.table_stock.available_quantity, 7)
        self.assertEqual(self.delivery_stock.available_quantity, 4)
        self.assertEqual(movement.quantity, -3)
        self.assertEqual(movement.reason, StockMovement.Reason.RESERVATION)
        self.assertEqual(movement.reference_id, 71)
        self.assertEqual(movement.actor, self.actor)

    def test_daily_stock_uses_fifteen_as_default_alert_threshold(self):
        stock = DailyProductStock.objects.create(
            product=self.product,
            channel=DailyProductStock.Channel.TABLE,
            initial_quantity=20,
            chicken_piece="leg",
        )

        self.assertEqual(stock.low_stock_threshold, 15)

    def test_allows_a_reservation_that_makes_stock_negative(self):
        reserve_stock(
            stock=self.delivery_stock, quantity=5, actor=self.actor,
            reference_type="order", reference_id=120,
        )
        self.assertEqual(self.delivery_stock.movements.count(), 1)
        self.assertEqual(self.delivery_stock.available_quantity, -1)

    def test_release_returns_reserved_stock(self):
        reserve_stock(
            stock=self.table_stock, quantity=2, actor=self.actor,
            reference_type="table_account", reference_id=71,
        )
        release_stock(
            stock=self.table_stock, quantity=1, actor=self.actor,
            reference_type="table_account", reference_id=71,
        )

        self.assertEqual(self.table_stock.available_quantity, 9)

    def test_manual_adjustment_is_audited_and_can_make_stock_negative(self):
        movement = adjust_stock(
            stock=self.table_stock, quantity=-2, actor=self.actor,
            note="Merma detectada en conteo físico",
        )
        self.assertEqual(self.table_stock.available_quantity, 8)
        self.assertEqual(movement.reason, StockMovement.Reason.ADJUSTMENT)
        self.assertEqual(movement.actor, self.actor)
        adjust_stock(
            stock=self.table_stock, quantity=-9, actor=self.actor,
            note="Merma adicional",
        )
        self.assertEqual(self.table_stock.available_quantity, -1)

    def test_transfer_moves_stock_between_channels_with_two_movements(self):
        transfer_stock(
            source=self.table_stock, target=self.delivery_stock, quantity=3,
            actor=self.actor, note="Mayor demanda en mostrador",
        )
        self.assertEqual(self.table_stock.available_quantity, 7)
        self.assertEqual(self.delivery_stock.available_quantity, 7)
        self.assertEqual(
            self.table_stock.movements.get().reason,
            StockMovement.Reason.TRANSFER_OUT,
        )
        self.assertEqual(
            self.delivery_stock.movements.get().reason,
            StockMovement.Reason.TRANSFER_IN,
        )


class InventoryControlViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="inventory_view_admin", password="test-password",
        )
        category = Category.objects.create(name="Productos vigilados")
        self.product = Product.objects.create(
            category=category, name="Producto vigilado", price=50,
        )
        self.stock = DailyProductStock.objects.create(
            stock_type=DailyProductStock.StockType.FIXED,
            date=None, product=self.product,
            channel=DailyProductStock.Channel.SHARED,
            initial_quantity=8, low_stock_threshold=3,
        )
        self.client.force_login(self.admin)

    def make_daily_stock(self):
        return DailyProductStock.objects.create(
            date=timezone.localdate(), product=self.product,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=2,
        )

    def test_saving_fixed_inventory_locks_only_stock_rows(self):
        response = self.client.post(reverse("menu:inventory_control"), {
            "action": "save_fixed",
            f"fixed_stock_{self.stock.pk}": "6",
            f"fixed_threshold_{self.stock.pk}": "2",
        })

        self.assertRedirects(response, reverse("menu:inventory_control"))
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available_quantity, 6)
        self.assertEqual(self.stock.low_stock_threshold, 2)

    def test_tracking_view_displays_negative_free_stock(self):
        daily = self.make_daily_stock()
        reserve_stock(
            stock=daily, quantity=3, actor=self.admin,
            reference_type="order_item", reference_id=999999,
        )

        response = self.client.get(reverse("menu:inventory_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Producto vigilado")
        self.assertContains(response, "Ver comprometidas (3)")
        self.assertContains(response, ">-1<", html=False)

    def test_tracking_cards_follow_kitchen_course_order(self):
        category = self.product.category
        definitions = (
            ("Sopa", Product.ComponentType.CHICKEN_CONSOMME),
            ("Arroz", Product.ComponentType.SECOND_COURSE),
            ("Guisado", Product.ComponentType.BEEF_STEW),
            ("Frijoles", Product.ComponentType.COMPLEMENT),
            ("Agua", Product.ComponentType.DAILY_WATER),
        )
        for name, component_type in definitions:
            product = Product.objects.create(
                category=category, name=name, price=10, component_type=component_type,
            )
            DailyProductStock.objects.create(
                date=timezone.localdate(), product=product,
                channel=DailyProductStock.Channel.ORDERS, initial_quantity=5,
            )
        for item_kind in (DailyProductStock.ItemKind.TORTILLAS, DailyProductStock.ItemKind.BREAD):
            DailyProductStock.objects.create(
                date=timezone.localdate(), item_kind=item_kind,
                channel=DailyProductStock.Channel.ORDERS, initial_quantity=5,
            )

        response = self.client.get(reverse("menu:inventory_tracking"))

        names = [row["name"] for row in response.context["rows"]]
        self.assertEqual(names, [
            "Sopa", "Arroz", "Guisado", "Porción de tortillas",
            "Frijoles", "Agua", "Bolillo",
        ])

    def test_waiter_and_delivery_can_read_but_cannot_edit_tracking(self):
        daily = self.make_daily_stock()
        for role in (WAITER, DELIVERY):
            with self.subTest(role=role):
                user = get_user_model().objects.create_user(username=f"readonly-{role}")
                user.groups.add(Group.objects.get_or_create(name=role)[0])
                self.client.force_login(user)
                response = self.client.get(reverse("menu:inventory_tracking"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Vista de consulta")
                self.assertNotContains(response, "stock-prepared-form")
                response = self.client.post(reverse("menu:inventory_tracking"), {
                    "action": "set_prepared", "date": timezone.localdate().isoformat(),
                    "stock_id": daily.pk, "prepared": "30",
                })
                self.assertEqual(response.status_code, 403)
                self.assertEqual(daily.available_quantity, 2)

    def test_waiter_remains_read_only_if_telephone_group_was_also_assigned(self):
        daily = self.make_daily_stock()
        user = get_user_model().objects.create_user(username="waiter-with-extra-group")
        user.groups.add(
            Group.objects.get_or_create(name=WAITER)[0],
            Group.objects.get_or_create(name=ORDER_TAKER)[0],
        )
        self.client.force_login(user)

        response = self.client.get(reverse("menu:inventory_tracking"))
        self.assertContains(response, "Vista de consulta")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        response = self.client.post(reverse("menu:inventory_tracking"), {
            "action": "set_prepared", "date": timezone.localdate().isoformat(),
            "stock_id": daily.pk, "prepared": "30", "alert_threshold": "9",
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(daily.available_quantity, 2)

    def test_order_taker_can_edit_tracking(self):
        daily = self.make_daily_stock()
        table_stock = DailyProductStock.objects.create(
            date=timezone.localdate(), product=self.product,
            channel=DailyProductStock.Channel.TABLE, initial_quantity=3,
        )
        user = get_user_model().objects.create_user(username="tracking-order-taker")
        user.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        self.client.force_login(user)

        # Cada canal se edita por separado: Pedidos sube de 2 a 4 piezas con alerta 4;
        # Mesas conserva sus 3 piezas y sólo cambia su alerta a 2.
        response = self.client.post(reverse("menu:inventory_tracking"), {
            "action": "set_prepared", "date": timezone.localdate().isoformat(),
            "stock_id": daily.pk,
            f"prepared_{daily.pk}": "4", f"alert_{daily.pk}": "4",
            f"prepared_{table_stock.pk}": "3", f"alert_{table_stock.pk}": "2",
        })

        self.assertEqual(response.status_code, 302)
        daily.refresh_from_db()
        table_stock.refresh_from_db()
        self.assertEqual(daily.available_quantity, 4)
        self.assertEqual(table_stock.available_quantity, 3)
        self.assertEqual(daily.low_stock_threshold, 4)
        self.assertEqual(table_stock.low_stock_threshold, 2)
        self.assertFalse(table_stock.movements.exists())
        audits = {audit.stock_id: audit for audit in InventoryAuditLog.objects.all()}
        self.assertEqual(len(audits), 2)
        self.assertEqual(audits[daily.pk].actor, user)
        self.assertEqual((audits[daily.pk].prepared_before, audits[daily.pk].prepared_after), (2, 4))
        self.assertEqual((audits[daily.pk].threshold_before, audits[daily.pk].threshold_after), (15, 4))
        self.assertEqual((audits[table_stock.pk].prepared_before, audits[table_stock.pk].prepared_after), (3, 3))
        self.assertEqual((audits[table_stock.pk].threshold_before, audits[table_stock.pk].threshold_after), (15, 2))
        response = self.client.get(reverse("menu:inventory_audit"))
        self.assertContains(response, "tracking-order-taker")

    def test_tracking_splits_each_product_by_channel(self):
        orders = self.make_daily_stock()
        table = DailyProductStock.objects.create(
            date=timezone.localdate(), product=self.product,
            channel=DailyProductStock.Channel.TABLE, initial_quantity=5, low_stock_threshold=1,
        )
        reserve_stock(stock=table, quantity=2, actor=self.admin, reference_type="table_item", reference_id=999998)
        reserve_stock(stock=orders, quantity=3, actor=self.admin, reference_type="order_item", reference_id=999999)

        response = self.client.get(reverse("menu:inventory_tracking"))

        row = response.context["rows"][0]
        self.assertEqual((row["prepared"], row["committed"], row["free"]), (7, 5, 2))
        channels = {channel["channel"]: channel for channel in row["channels"]}
        self.assertEqual([channel["label"] for channel in row["channels"]], ["Mesas", "Pedidos"])
        self.assertEqual(
            (channels["table"]["prepared"], channels["table"]["committed"], channels["table"]["free"], channels["table"]["status"]),
            (5, 2, 3, "ok"),
        )
        self.assertEqual(
            (channels["orders"]["prepared"], channels["orders"]["committed"], channels["orders"]["free"], channels["orders"]["status"]),
            (2, 3, -1, "deficit"),
        )
        self.assertContains(response, f'name="prepared_{table.pk}"')
        self.assertContains(response, f'name="alert_{orders.pk}"')
        self.assertContains(response, 'data-reference-channel="orders"')
        totals = {item["label"]: item for item in response.context["channel_totals"]}
        self.assertEqual((totals["Mesas"]["committed"], totals["Pedidos"]["committed"]), (2, 3))
        # El filtro "Rebasado" encuentra el producto porque Pedidos está rebasado.
        response = self.client.get(reverse("menu:inventory_tracking"), {"status": "deficit"})
        self.assertEqual(len(response.context["rows"]), 1)

    def test_inventory_history_filters_and_summarizes_movements(self):
        adjust_stock(
            stock=self.stock, quantity=-2, actor=self.admin,
            note="Reconteo de prueba",
        )
        adjust_stock(
            stock=self.stock, quantity=1, actor=self.admin,
            note="Entrada de prueba",
        )

        response = self.client.get(reverse("menu:inventory_history"), {
            "stock_type": DailyProductStock.StockType.FIXED,
            "channel": DailyProductStock.Channel.SHARED,
            "q": "vigilado",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reconteo de prueba")
        self.assertContains(response, "Entrada de prueba")
        self.assertEqual(response.context["movement_count"], 2)
        self.assertEqual(response.context["entry_total"], 1)
        self.assertEqual(response.context["exit_total"], 2)

    def test_inventory_history_is_paginated(self):
        StockMovement.objects.bulk_create([
            StockMovement(
                stock=self.stock, quantity=-1,
                reason=StockMovement.Reason.RESERVATION,
            )
            for _index in range(31)
        ])

        response = self.client.get(reverse("menu:inventory_history"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page"].object_list), 30)
        self.assertContains(response, "Página 1 de 2")


class ProductDeleteViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="product_delete_admin", password="test-password",
        )
        self.category = Category.objects.create(name="Categoría de prueba")
        self.client.force_login(self.admin)

    def test_deletes_product_without_protected_relations(self):
        product = Product.objects.create(category=self.category, name="Sin uso", price=30)

        response = self.client.post(
            reverse("menu:product_delete", args=(product.pk,)), follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_deleting_a_product_with_daily_stock_deletes_its_history(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: reproduce el bug reportado en producción
        # (500 al eliminar un producto en /app/menu/productos/<id>/eliminar/) — el
        # producto tenía un registro de `DailyProductStock`, protegido con
        # `on_delete=PROTECT`, y la vista no capturaba el `ProtectedError`. Borra
        # esta nota después de leerla.
        product = Product.objects.create(category=self.category, name="Con existencias", price=30)
        DailyProductStock.objects.create(product=product, initial_quantity=5)

        response = self.client.post(
            reverse("menu:product_delete", args=(product.pk,)), follow=True,
        )

        # Regla del dueño (2026-10-09): el historial de inventario ya no bloquea; se borra
        # junto con el producto (sin error 500).
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(DailyProductStock.objects.filter(product_id=product.pk).exists())

    def test_confirm_page_warns_history_will_be_deleted(self):
        product = Product.objects.create(category=self.category, name="Con existencias", price=30)
        DailyProductStock.objects.create(product=product, initial_quantity=5)

        response = self.client.get(reverse("menu:product_delete", args=(product.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["blocked"])
        self.assertContains(response, "También se borrará su historial")


class OptionGroupsAlwaysMultipleTests(TestCase):
    def test_single_choice_is_saved_as_multiple(self):
        import json
        from menu.customization import parse_customization_payload
        groups = parse_customization_payload(json.dumps([{
            "name": "Leche", "selection_type": "single", "is_required": False,
            "options": [
                {"name": "Entera", "price_adjustment": "0", "is_default": True, "is_available": True},
                {"name": "Deslactosada", "price_adjustment": "0", "is_default": True, "is_available": True},
            ],
        }]))
        self.assertEqual(groups[0]["selection_type"], "multiple")


class DailyMenuStewListTests(TestCase):
    """Tercer tiempo con hasta 12 guisados de cualquier tipo (los de pollo piden pieza)."""

    def setUp(self):
        from menu.models import Category
        category = Category.objects.create(name="Guisados lista")
        make = lambda name, kind: Product.objects.create(category=category, name=name, price=0, component_type=kind)
        self.stews = [
            make("Pollo a la ciruela", Product.ComponentType.CHICKEN_STEW),
            make("Res en estofado", Product.ComponentType.BEEF_STEW),
            make("Bistec en salsa verde", Product.ComponentType.BEEF_STEW),
            make("Pollo en mole", Product.ComponentType.CHICKEN_STEW),
            make("Enchiladas suizas", Product.ComponentType.VARIED_STEW),
        ]

    def form_data(self, stews):
        from menu.models import DailyProductStock
        data = {"date": timezone.localdate().isoformat()}
        for kind in (DailyProductStock.ItemKind.TORTILLAS, DailyProductStock.ItemKind.BREAD):
            for channel in (DailyProductStock.Channel.TABLE, DailyProductStock.Channel.ORDERS):
                data[f"stock_{kind}_{channel}"] = "5"
        for slot, product in enumerate(stews, start=1):
            data[f"stew_{slot}"] = str(product.pk)
            pieces = ("leg", "thigh") if product.component_type == Product.ComponentType.CHICKEN_STEW else ("",)
            for piece in pieces:
                suffix = f"_{piece}" if piece else ""
                data[f"stock_stew_{slot}{suffix}_table"] = "4"
                data[f"stock_stew_{slot}{suffix}_orders"] = "3"
        return data

    def test_form_saves_five_stews_in_order_with_chicken_pieces(self):
        from menu.forms import DailyMenuForm
        from menu.models import DailyProductStock
        form = DailyMenuForm(self.form_data(self.stews))
        self.assertTrue(form.is_valid(), form.errors)
        menu = form.save()
        form.save_stocks()
        self.assertEqual([product.name for product in menu.stew_products], [product.name for product in self.stews])
        self.assertEqual(set(menu.chicken_stew_ids), {self.stews[0].pk, self.stews[3].pk})
        mole_pieces = set(DailyProductStock.objects.filter(product=self.stews[3]).values_list("chicken_piece", flat=True))
        self.assertEqual(mole_pieces, {"leg", "thigh"})
        beef_pieces = set(DailyProductStock.objects.filter(product=self.stews[1]).values_list("chicken_piece", flat=True))
        self.assertEqual(beef_pieces, {""})
        # Al editar se conservan los 5 renglones y sus raciones.
        edit = DailyMenuForm(instance=menu)
        self.assertEqual(edit.visible_stew_rows, 5)
        self.assertEqual(edit.initial["stock_stew_4_leg_table"], 4)

    def test_repeated_stew_is_rejected(self):
        from menu.forms import DailyMenuForm
        form = DailyMenuForm(self.form_data([self.stews[1], self.stews[1]]))
        self.assertFalse(form.is_valid())
        self.assertIn("stew_2", form.errors)

    def test_any_chicken_stew_requires_piece_in_package(self):
        from orders.forms import PackageCartForm
        from menu.models import DailyMenu, MealPackage
        menu = DailyMenu.objects.create(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        menu.set_stews(self.stews)
        package, _ = MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={"name": "Comida corrida", "price_without_water": 70, "price_with_water": 80},
        )
        form = PackageCartForm(package=package, daily_menu=menu)
        self.assertEqual(list(form.fields["main_course"].queryset), self.stews)
        self.assertTrue(menu.is_chicken_stew(self.stews[3]))
        self.assertFalse(menu.is_chicken_stew(self.stews[2]))
