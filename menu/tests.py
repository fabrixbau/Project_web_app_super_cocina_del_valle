from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .catalog import limit_cold_drinks_to_daily_water
from .inventory import adjust_stock, release_stock, reserve_stock, transfer_stock
from .models import Category, DailyProductStock, Product, StockMovement


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

    def test_rejects_a_reservation_that_would_make_stock_negative(self):
        with self.assertRaisesMessage(ValidationError, "Disponibles: 4"):
            reserve_stock(
                stock=self.delivery_stock,
                quantity=5,
                actor=self.actor,
                reference_type="order",
                reference_id=120,
            )

        self.assertEqual(self.delivery_stock.movements.count(), 0)
        self.assertEqual(self.delivery_stock.available_quantity, 4)

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

    def test_manual_adjustment_is_audited_and_cannot_make_stock_negative(self):
        movement = adjust_stock(
            stock=self.table_stock, quantity=-2, actor=self.actor,
            note="Merma detectada en conteo físico",
        )
        self.assertEqual(self.table_stock.available_quantity, 8)
        self.assertEqual(movement.reason, StockMovement.Reason.ADJUSTMENT)
        self.assertEqual(movement.actor, self.actor)
        with self.assertRaisesMessage(ValidationError, "Disponibles: 8"):
            adjust_stock(
                stock=self.table_stock, quantity=-9, actor=self.actor,
                note="Corrección inválida",
            )

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

    def test_deleting_a_product_with_daily_stock_shows_error_instead_of_500(self):
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

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertContains(response, "No puedes eliminar")

    def test_confirm_page_shows_blocked_state_for_product_with_daily_stock(self):
        product = Product.objects.create(category=self.category, name="Con existencias", price=30)
        DailyProductStock.objects.create(product=product, initial_quantity=5)

        response = self.client.get(reverse("menu:product_delete", args=(product.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["blocked"])
        self.assertContains(response, "inventario diario")
