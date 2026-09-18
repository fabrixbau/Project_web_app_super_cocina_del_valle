from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER

from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product, StockMovement

from .models import Order
from .services import (
    add_internal_order_package, add_internal_order_product, change_internal_order_item,
    change_internal_order_type, transition_order, update_cashier_payment, update_delivery_tip,
    update_internal_package_extras,
)


class OrderPaymentPermissionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.telefonista = user_model.objects.create_user(username="payment_order_taker")
        self.telefonista.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        self.mesero = user_model.objects.create_user(username="payment_waiter")
        self.mesero.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.admin = user_model.objects.create_user(username="payment_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])

    def make_order(self, *, order_type, status):
        return Order.objects.create(
            daily_number=980 + Order.objects.count(), operating_date=timezone.localdate(),
            order_type=order_type, source=Order.Source.INTERNAL, status=status,
            customer_name="Cliente pago", total=100,
            payment_method=Order.PaymentMethod.CASH,
        )

    def assert_payment_blocked(self, *, actor, order):
        with self.assertRaisesMessage(ValidationError, "estado actual"):
            update_cashier_payment(
                order=order, payment_method=Order.PaymentMethod.CARD,
                cash_amount="", actor=actor,
            )
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CASH)

    def test_telefonista_cannot_change_delivery_payment_in_delivery_or_delivered(self):
        for status in (Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED):
            with self.subTest(status=status):
                self.assert_payment_blocked(
                    actor=self.telefonista,
                    order=self.make_order(order_type=Order.OrderType.DELIVERY, status=status),
                )

    def test_mesero_cannot_change_delivery_payment_in_delivery_or_delivered(self):
        for status in (Order.Status.OUT_FOR_DELIVERY, Order.Status.DELIVERED):
            with self.subTest(status=status):
                self.assert_payment_blocked(
                    actor=self.mesero,
                    order=self.make_order(order_type=Order.OrderType.DELIVERY, status=status),
                )

    def test_telefonista_and_mesero_cannot_change_picked_up_payment(self):
        for actor in (self.telefonista, self.mesero):
            with self.subTest(actor=actor.username):
                self.assert_payment_blocked(
                    actor=actor,
                    order=self.make_order(
                        order_type=Order.OrderType.PICKUP, status=Order.Status.PICKED_UP,
                    ),
                )

    def test_restarted_cycle_allows_telefonista_and_mesero_again(self):
        for actor in (self.telefonista, self.mesero):
            with self.subTest(actor=actor.username):
                order = self.make_order(
                    order_type=Order.OrderType.DELIVERY, status=Order.Status.PENDING_CONFIRMATION,
                )
                update_cashier_payment(
                    order=order, payment_method=Order.PaymentMethod.CARD,
                    cash_amount="", actor=actor,
                )
                order.refresh_from_db()
                self.assertEqual(order.payment_method, Order.PaymentMethod.CARD)

    def test_administrator_can_change_payment_in_final_status(self):
        order = self.make_order(
            order_type=Order.OrderType.PICKUP, status=Order.Status.PICKED_UP,
        )
        update_cashier_payment(
            order=order, payment_method=Order.PaymentMethod.TRANSFER,
            cash_amount="", actor=self.admin,
        )
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.TRANSFER)

    def test_order_list_hides_payment_buttons_when_locked(self):
        order = self.make_order(
            order_type=Order.OrderType.PICKUP, status=Order.Status.PICKED_UP,
        )
        self.client.force_login(self.mesero)
        response = self.client.get(reverse("orders:order_list"), {"scope": "completed"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.formatted_number)
        self.assertNotContains(response, "data-order-payment-method")


class DeliveryProfileRestrictionTests(TestCase):
    def setUp(self):
        self.courier = get_user_model().objects.create_user(username="restricted_courier")
        self.courier.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.other_courier = get_user_model().objects.create_user(username="other_courier")
        self.other_courier.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.order = Order.objects.create(
            daily_number=979, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.OUT_FOR_DELIVERY, customer_name="Entrega restringida",
            total=100, payment_method=Order.PaymentMethod.CASH,
            delivery_person=self.courier,
        )
        self.client.force_login(self.courier)

    def test_courier_cannot_assign_orders_or_change_status(self):
        assign_response = self.client.post(
            reverse("deliveries:delivery_assign", args=(self.order.pk,)),
            {"delivery_person": self.courier.pk},
        )
        self.assertEqual(assign_response.status_code, 403)
        status_response = self.client.post(
            reverse("deliveries:delivery_complete", args=(self.order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(status_response.status_code, 403)

    def test_courier_only_sees_assigned_orders(self):
        unassigned = Order.objects.create(
            daily_number=978, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.READY, customer_name="Sin asignar", total=80,
            payment_method=Order.PaymentMethod.CARD,
        )
        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertContains(response, self.order.formatted_number)
        self.assertNotContains(response, unassigned.formatted_number)
        self.assertNotContains(response, "Asignarme este pedido")

    def test_courier_can_register_cash_tip_only_once(self):
        update_delivery_tip(order=self.order, amount=10, actor=self.courier)
        self.order.refresh_from_db()
        self.assertEqual(self.order.delivery_tip_amount, 10)
        with self.assertRaisesMessage(ValidationError, "ya fue registrada"):
            update_delivery_tip(order=self.order, amount=20, actor=self.courier)

    def test_courier_cannot_register_transfer_tip(self):
        self.order.payment_method = Order.PaymentMethod.TRANSFER
        self.order.save(update_fields=("payment_method",))
        with self.assertRaisesMessage(ValidationError, "Efectivo o Terminal"):
            update_delivery_tip(order=self.order, amount=10, actor=self.courier)


class CapturePrintTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="print_capture_admin", email="capture@example.test", password="test-password",
        )
        self.order = Order.objects.create(
            daily_number=992, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", phone="", total=38,
            created_by=self.actor,
        )
        self.client.force_login(self.actor)

    def test_new_capture_exposes_print_actions_before_first_item(self):
        response = self.client.get(reverse("orders:internal_order_edit", args=(self.order.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-internal-print-urls")
        self.assertContains(response, reverse("orders:order_payment_print", args=(self.order.pk,)))

    def test_print_autosave_persists_cash_before_queue(self):
        response = self.client.post(reverse("orders:internal_order_customer_autosave", args=(self.order.pk,)), {
            "order_type": "pickup", "customer_name": "Mostrador", "payment_method": "cash",
            "cash_bill": "200", "for_print": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.cash_tendered, 200)
        self.assertTrue(self.order.needs_change)

    def test_print_autosave_rejects_insufficient_cash(self):
        response = self.client.post(reverse("orders:internal_order_customer_autosave", args=(self.order.pk,)), {
            "order_type": "pickup", "customer_name": "Mostrador", "payment_method": "cash",
            "cash_bill": "20", "for_print": "1",
        })
        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.cash_tendered)


class InternalOrderReservedCategoryTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="reserved_category_admin", email="reserved@example.test",
            password="test-password",
        )
        category = Category.objects.create(
            name="Comida por orden", show_on_table_lunch=True,
        )
        self.bread = Product.objects.create(
            category=category, name="Bolillo", price=5,
            is_available=True, is_sold_individually=True,
            uses_bread_stock=True,
        )
        DailyProductStock.objects.create(
            date=timezone.localdate(), item_kind=DailyProductStock.ItemKind.BREAD,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=20,
        )
        self.order = Order.objects.create(
            daily_number=993, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=0,
            created_by=self.actor,
        )
        self.client.force_login(self.actor)
        session = self.client.session
        session["internal_order_menu_mode"] = "lunch"
        session.save()

    def test_loose_product_in_daily_order_category_is_visible_and_searchable(self):
        response = self.client.get(reverse("orders:internal_order_edit", args=(self.order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-product-name="bolillo"')
        self.assertContains(
            response,
            reverse("orders:internal_order_product_add", args=(self.order.pk, self.bread.pk)),
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
