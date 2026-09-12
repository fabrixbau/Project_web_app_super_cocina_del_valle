from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN

from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product, StockMovement

from .models import Order
from .services import (
    add_internal_order_package, add_internal_order_product, change_internal_order_item,
    change_internal_order_type, transition_order, update_internal_package_extras,
)


class OrderInventoryIntegrationTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="stock_order_taker")
        category = Category.objects.create(name="Segundos de prueba")
        self.product = Product.objects.create(
            category=category, name="Arroz inventario", price=25,
            component_type=Product.ComponentType.SECOND_COURSE,
            is_sold_individually=False,
        )
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(
            date=today, status=DailyMenu.Status.PUBLISHED,
            second_course_one=self.product,
        )
        self.pickup_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.product,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=2,
        )
        self.order = Order.objects.create(
            daily_number=991, operating_date=today,
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", phone="", total=0,
            created_by=self.actor,
        )

    def test_item_changes_reserve_and_release_pickup_stock(self):
        item = add_internal_order_product(
            order=self.order, product=self.product, actor=self.actor,
            require_individual=False,
        )
        self.assertEqual(self.pickup_stock.available_quantity, 1)
        change_internal_order_item(order=self.order, item=item, action="increase", actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, 0)
        with self.assertRaisesMessage(ValidationError, "Disponibles: 0"):
            change_internal_order_item(order=self.order, item=item, action="increase", actor=self.actor)
        change_internal_order_item(order=self.order, item=item, action="remove", actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, 2)

    def test_switching_between_pickup_and_delivery_keeps_the_same_reservation(self):
        add_internal_order_product(order=self.order, product=self.product, actor=self.actor, require_individual=False)
        change_internal_order_type(order=self.order, order_type=Order.OrderType.DELIVERY, actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, 1)

    def test_cancel_returns_stock(self):
        self.actor.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        item = add_internal_order_product(order=self.order, product=self.product, actor=self.actor, require_individual=False)
        self.order.status = Order.Status.PENDING_CONFIRMATION
        self.order.save(update_fields=("status",))
        transition_order(order=self.order, action="cancel", actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, 2)
        self.assertTrue(item.pk and self.pickup_stock.movements.filter(reason=StockMovement.Reason.RELEASE).exists())

    def test_only_administrator_can_cancel(self):
        self.order.status = Order.Status.PREPARING
        self.order.save(update_fields=("status",))
        with self.assertRaisesMessage(ValidationError, "Sólo un administrador"):
            transition_order(order=self.order, action="cancel", actor=self.actor)

    def test_cash_exact_is_the_amount_the_courier_returns(self):
        self.order.payment_method = Order.PaymentMethod.CASH
        self.order.total = 38
        self.order.cash_tendered = 38
        self.order.needs_change = False
        self.assertEqual(self.order.courier_return_amount, 38)

    def test_cash_bill_is_the_amount_the_courier_returns(self):
        self.order.payment_method = Order.PaymentMethod.CASH
        self.order.total = 50
        self.order.cash_tendered = 200
        self.order.needs_change = True
        self.assertEqual(self.order.change_required, 150)
        self.assertEqual(self.order.courier_return_amount, 200)

    def test_change_board_totals_include_settled_cash_while_showing_pending(self):
        admin_group = Group.objects.get_or_create(name=ADMIN)[0]
        self.actor.groups.add(admin_group)
        courier = get_user_model().objects.create_user(username="courier_summary")
        settled = Order.objects.create(
            daily_number=993, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Cliente prueba", total=50,
            payment_method=Order.PaymentMethod.CASH, cash_tendered=200,
            needs_change=True, delivery_person=courier,
            cashier_released_at=timezone.now(), cash_settlement_confirmed=True,
        )
        self.client.force_login(self.actor)
        response = self.client.get(reverse("cashier:change_board"), {"settlement": "pending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["settled_total"], settled.courier_return_amount)

    def test_completed_pickup_marks_reservation_as_consumption(self):
        item = add_internal_order_product(order=self.order, product=self.product, actor=self.actor, require_individual=False)
        self.order.status = Order.Status.READY
        self.order.payment_method = Order.PaymentMethod.CASH
        self.order.cash_tendered = 25
        self.order.save(update_fields=("status", "payment_method", "cash_tendered"))
        transition_order(order=self.order, action="complete_pickup", actor=self.actor)
        movement = self.pickup_stock.movements.get(reference_id=item.pk)
        self.assertEqual(movement.reason, StockMovement.Reason.CONSUMPTION)
        self.assertEqual(self.pickup_stock.available_quantity, 1)


class OrderPackageInventoryTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="package_stock_user")
        category = Category.objects.create(name="Paquetes inventario")
        self.product = Product.objects.create(
            category=category, name="Componente paquete", price=20,
            component_type=Product.ComponentType.SECOND_COURSE,
            is_sold_individually=False,
        )
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(
            date=today, status=DailyMenu.Status.PUBLISHED,
            second_course_one=self.product,
        )
        self.product_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.product,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=10,
        )
        self.tortilla_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=None,
            item_kind=DailyProductStock.ItemKind.TORTILLAS,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=5,
        )
        self.bread_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=None,
            item_kind=DailyProductStock.ItemKind.BREAD,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=5,
        )
        self.package, _ = MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={
                "name": "Paquete prueba",
                "price_without_water": 70,
                "price_with_water": 80,
                "table_refill_price": 10,
            },
        )
        self.order = Order.objects.create(
            daily_number=992, operating_date=today, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=0, created_by=self.actor,
        )

    def test_editing_package_swaps_only_its_supplies(self):
        item = add_internal_order_package(
            order=self.order, package=self.package, daily_menu=self.menu,
            actor=self.actor,
            cleaned_data={
                "first_course": self.product, "second_course": self.product,
                "main_course": self.product, "chicken_piece": "",
                "with_water": False, "tortillas": "yes", "bread": False,
                "beans": "no", "quantity": 1, "customization_comment": "",
            },
        )
        self.assertEqual(self.product_stock.available_quantity, 7)
        self.assertEqual(self.tortilla_stock.available_quantity, 4)

        update_internal_package_extras(
            order=self.order, item=item, actor=self.actor,
            cleaned_data={
                "with_water": False, "tortillas": False, "bread": True,
                "beans": False, "customization_comment": "",
            },
        )
        item.refresh_from_db()
        self.assertEqual(item.daily_menu, self.menu)
        self.assertEqual(self.product_stock.available_quantity, 7)
        self.assertEqual(self.tortilla_stock.available_quantity, 5)
        self.assertEqual(self.bread_stock.available_quantity, 4)


class ChickenPieceInventoryTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="chicken_stock_user")
        category = Category.objects.create(name="Guisados de pollo inventario")
        self.chicken = Product.objects.create(
            category=category, name="Pollo de prueba", price=45,
            component_type=Product.ComponentType.CHICKEN_STEW,
            is_sold_individually=False,
        )
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(
            date=today, status=DailyMenu.Status.PUBLISHED, chicken_stew=self.chicken,
        )
        self.legs = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.chicken,
            channel=DailyProductStock.Channel.ORDERS,
            chicken_piece=DailyProductStock.ChickenPiece.LEG, initial_quantity=2,
        )
        self.thighs = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.chicken,
            channel=DailyProductStock.Channel.ORDERS,
            chicken_piece=DailyProductStock.ChickenPiece.THIGH, initial_quantity=3,
        )
        self.order = Order.objects.create(
            daily_number=993, operating_date=today, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=0, created_by=self.actor,
        )

    def test_each_chicken_piece_uses_its_own_stock(self):
        add_internal_order_product(
            order=self.order, product=self.chicken, actor=self.actor,
            require_individual=False, chicken_piece="leg", daily_menu=self.menu,
        )
        self.assertEqual(self.legs.available_quantity, 1)
        self.assertEqual(self.thighs.available_quantity, 3)


class FixedMenuInventoryTests(TestCase):
    def test_pickup_and_delivery_share_one_fixed_product_stock(self):
        actor = get_user_model().objects.create_user(username="fixed_stock_user")
        category = Category.objects.create(name="Menú fijo inventario")
        product = Product.objects.create(
            category=category, name="Hamburguesa fija", price=90,
            is_sold_individually=True,
        )
        stock = DailyProductStock.objects.create(
            stock_type=DailyProductStock.StockType.FIXED,
            date=None, product=product, channel=DailyProductStock.Channel.SHARED,
            initial_quantity=3,
        )
        pickup = Order.objects.create(
            daily_number=994, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", phone="",
            total=0, created_by=actor,
        )
        delivery = Order.objects.create(
            daily_number=995, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Entrega", phone="5555555555",
            total=0, created_by=actor,
        )

        add_internal_order_product(order=pickup, product=product, actor=actor)
        add_internal_order_product(order=delivery, product=product, actor=actor)

        self.assertEqual(stock.available_quantity, 1)
        self.assertEqual(stock.movements.count(), 2)
