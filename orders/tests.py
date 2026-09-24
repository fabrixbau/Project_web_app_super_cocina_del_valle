from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER

from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product, StockMovement

from tables.models import DiningTable, TableAccount

from .models import Order, TerminalCut, TerminalMovement
from .services import (
    add_internal_order_package, add_internal_order_product, assign_delivery,
    change_internal_order_item, change_internal_order_type, set_cashier_release, transition_order,
    update_cashier_payment, update_delivery_tip, update_internal_package_extras,
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

    def test_courier_can_complete_own_card_or_transfer_delivery(self):
        for payment_method in (Order.PaymentMethod.CARD, Order.PaymentMethod.TRANSFER):
            with self.subTest(payment_method=payment_method):
                order = Order.objects.create(
                    daily_number=970 + list(Order.PaymentMethod).index(payment_method),
                    operating_date=timezone.localdate(),
                    order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
                    status=Order.Status.OUT_FOR_DELIVERY, customer_name="Entrega tarjeta",
                    total=100, payment_method=payment_method, delivery_person=self.courier,
                )
                response = self.client.post(
                    reverse("deliveries:delivery_complete", args=(order.pk,)),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(response.status_code, 200)
                order.refresh_from_db()
                self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_courier_still_cannot_complete_own_cash_delivery(self):
        response = self.client.post(
            reverse("deliveries:delivery_complete", args=(self.order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.OUT_FOR_DELIVERY)

    def test_courier_cannot_complete_someone_elses_order(self):
        other_order = Order.objects.create(
            daily_number=977, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.OUT_FOR_DELIVERY, customer_name="Otro repartidor",
            total=100, payment_method=Order.PaymentMethod.CARD,
            delivery_person=self.other_courier,
        )
        response = self.client.post(
            reverse("deliveries:delivery_complete", args=(other_order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 403)

    def test_courier_can_register_card_tip_after_marking_delivered(self):
        card_order = Order.objects.create(
            daily_number=976, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Entrega ya cerrada",
            total=100, payment_method=Order.PaymentMethod.CARD,
            delivery_person=self.courier,
        )
        response = self.client.post(
            reverse("deliveries:delivery_tip_update", args=(card_order.pk,)),
            {"tip_amount": "15"},
        )
        self.assertEqual(response.status_code, 200)
        card_order.refresh_from_db()
        self.assertEqual(card_order.delivery_tip_amount, 15)

    def test_courier_cannot_register_cash_tip_after_delivered(self):
        cash_order = Order.objects.create(
            daily_number=975, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Efectivo ya entregado",
            total=100, payment_method=Order.PaymentMethod.CASH,
            delivery_person=self.courier,
        )
        response = self.client.post(
            reverse("deliveries:delivery_tip_update", args=(cash_order.pk,)),
            {"tip_amount": "10"},
        )
        self.assertEqual(response.status_code, 403)
        cash_order.refresh_from_db()
        self.assertIsNone(cash_order.delivery_tip_updated_at)


class CashierReleaseCashDefaultTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="release_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.today = timezone.localdate()

    def make_pickup_order(self, *, payment_method, cash_tendered=None, needs_change=False):
        return Order.objects.create(
            daily_number=940, operating_date=self.today,
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.READY, customer_name="Recoger caja", total=150,
            payment_method=payment_method, cash_tendered=cash_tendered, needs_change=needs_change,
        )

    def test_releasing_a_pickup_order_with_cash_and_no_amount_assumes_exact_payment(self):
        order = self.make_pickup_order(payment_method=Order.PaymentMethod.CASH)
        order = set_cashier_release(order=order, actor=self.admin, released=True)
        self.assertEqual(order.cash_tendered, order.total)
        self.assertFalse(order.needs_change)
        self.assertEqual(order.status, Order.Status.PICKED_UP)

    def test_releasing_a_pickup_order_keeps_an_already_defined_cash_amount(self):
        order = self.make_pickup_order(payment_method=Order.PaymentMethod.CASH, cash_tendered=200, needs_change=True)
        order = set_cashier_release(order=order, actor=self.admin, released=True)
        self.assertEqual(order.cash_tendered, 200)
        self.assertTrue(order.needs_change)

    def test_releasing_a_pickup_order_does_not_touch_non_cash_payment(self):
        order = self.make_pickup_order(payment_method=Order.PaymentMethod.CARD)
        order = set_cashier_release(order=order, actor=self.admin, released=True)
        self.assertIsNone(order.cash_tendered)
        self.assertFalse(order.needs_change)

    def test_advancing_status_directly_from_pedidos_also_assumes_exact_payment(self):
        # NOTA: mismo default, pero entrando por /app/pedidos/ (transition_order
        # directo) en vez de "Liberar de caja" — ambos caminos deben comportarse igual.
        order = self.make_pickup_order(payment_method=Order.PaymentMethod.CASH)
        order = transition_order(order=order, action="complete_pickup", actor=self.admin)
        self.assertEqual(order.cash_tendered, order.total)
        self.assertFalse(order.needs_change)
        self.assertEqual(order.status, Order.Status.PICKED_UP)
        self.assertFalse(order.needs_change)


class DeliveryTipTerminalMovementSyncTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="tip_sync_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.courier1 = get_user_model().objects.create_user(username="tip_sync_courier1")
        self.courier1.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.courier4 = get_user_model().objects.create_user(username="tip_sync_courier4")
        self.courier4.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.today = timezone.localdate()
        self.order = Order.objects.create(
            daily_number=950, operating_date=self.today,
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Entrega terminal",
            total=100, payment_method=Order.PaymentMethod.CARD,
            delivery_person=self.courier1, delivery_tip_amount=20,
            delivery_tip_recipient=self.courier1,
        )
        cut, _ = TerminalCut.objects.get_or_create(
            operating_date=self.today, provider=TerminalCut.Provider.MERCADO_PAGO,
        )
        self.movement = TerminalMovement.objects.create(
            cut=cut, order=self.order, total_amount=120, tip_amount=20,
            tip_recipient=self.courier1, created_by=self.admin,
        )

    def test_correcting_the_tip_amount_updates_the_linked_terminal_movement(self):
        update_delivery_tip(order=self.order, amount=10, actor=self.admin)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.tip_amount, 10)
        self.assertEqual(self.movement.total_amount, 110)
        self.assertEqual(self.movement.tip_recipient_id, self.courier1.pk)

    def test_reassigning_the_courier_updates_the_linked_terminal_movement_recipient(self):
        assign_delivery(order=self.order, delivery_person=self.courier4, assigned_by=self.admin)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.tip_recipient_id, self.courier4.pk)
        self.assertEqual(self.movement.total_amount, 120)

    def test_correcting_tip_and_reassigning_together_matches_the_users_scenario(self):
        update_delivery_tip(order=self.order, amount=10, actor=self.admin)
        assign_delivery(order=self.order, delivery_person=self.courier4, assigned_by=self.admin)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.tip_amount, 10)
        self.assertEqual(self.movement.total_amount, 110)
        self.assertEqual(self.movement.tip_recipient_id, self.courier4.pk)


class TerminalMovementLinkingRulesTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="terminal_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.waiter = get_user_model().objects.create_user(username="terminal_waiter")
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.client.force_login(self.admin)
        self.today = timezone.localdate()
        self.table = DiningTable.objects.create(name="Mesa terminal test")

    def make_delivery_order(self, *, daily_number, payment_method, status):
        return Order.objects.create(
            daily_number=daily_number, operating_date=self.today,
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=status, customer_name="Cliente terminal", total=100,
            payment_method=payment_method,
        )

    def make_closed_table(self, *, payment_method):
        return TableAccount.objects.create(
            table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter,
            status=TableAccount.Status.CLOSED, payment_method=payment_method,
            total_paid=100, closed_at=timezone.now(),
        )

    def save_movement(self, *, provider, linked_record, total_amount="100.00"):
        cut, _ = TerminalCut.objects.get_or_create(operating_date=self.today, provider=provider)
        return self.client.post(reverse("cashier:terminal_movement_save"), {
            "cut_id": cut.pk, "total_amount": total_amount, "tip_amount": "0",
            "linked_record": linked_record,
        })

    def test_clover_can_link_closed_card_table_but_not_a_delivery_order(self):
        table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.CARD)
        response = self.save_movement(provider=TerminalCut.Provider.CLOVER, linked_record=f"table:{table.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TerminalMovement.objects.get().table_account_id, table.pk)

        order = self.make_delivery_order(
            daily_number=901, payment_method=Order.PaymentMethod.CARD, status=Order.Status.DELIVERED,
        )
        response = self.save_movement(provider=TerminalCut.Provider.CLOVER, linked_record=f"order:{order.pk}")
        self.assertEqual(response.status_code, 400)

    def test_mercado_pago_can_link_delivered_card_order_but_not_a_table(self):
        order = self.make_delivery_order(
            daily_number=902, payment_method=Order.PaymentMethod.CARD, status=Order.Status.DELIVERED,
        )
        response = self.save_movement(provider=TerminalCut.Provider.MERCADO_PAGO, linked_record=f"order:{order.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TerminalMovement.objects.get().order_id, order.pk)

        table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.CARD)
        response = self.save_movement(provider=TerminalCut.Provider.MERCADO_PAGO, linked_record=f"table:{table.pk}")
        self.assertEqual(response.status_code, 400)

    def test_mercado_pago_rejects_order_still_out_for_delivery(self):
        order = self.make_delivery_order(
            daily_number=903, payment_method=Order.PaymentMethod.CARD,
            status=Order.Status.OUT_FOR_DELIVERY,
        )
        response = self.save_movement(provider=TerminalCut.Provider.MERCADO_PAGO, linked_record=f"order:{order.pk}")
        self.assertEqual(response.status_code, 400)

    def test_transfer_can_link_both_delivered_and_out_for_delivery_transfer_orders(self):
        for status in (Order.Status.DELIVERED, Order.Status.OUT_FOR_DELIVERY):
            with self.subTest(status=status):
                order = self.make_delivery_order(
                    daily_number=910 + list(Order.Status).index(status),
                    payment_method=Order.PaymentMethod.TRANSFER, status=status,
                )
                response = self.save_movement(provider=TerminalCut.Provider.TRANSFER, linked_record=f"order:{order.pk}")
                self.assertEqual(response.status_code, 200)

    def test_transfer_can_link_a_closed_transfer_table(self):
        table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.TRANSFER)
        response = self.save_movement(provider=TerminalCut.Provider.TRANSFER, linked_record=f"table:{table.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(TerminalMovement.objects.get().table_account_id, table.pk)

    def test_transfer_rejects_a_card_paid_table(self):
        table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.CARD)
        response = self.save_movement(provider=TerminalCut.Provider.TRANSFER, linked_record=f"table:{table.pk}")
        self.assertEqual(response.status_code, 400)

    def test_canceled_order_never_appears_as_linkable(self):
        self.make_delivery_order(
            daily_number=920, payment_method=Order.PaymentMethod.TRANSFER,
            status=Order.Status.CANCELED,
        )
        cut, _ = TerminalCut.objects.get_or_create(operating_date=self.today, provider=TerminalCut.Provider.TRANSFER)
        response = self.client.get(f"{reverse('cashier:terminal_board')}?provider=transfer")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["link_candidates"], [])


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


class KitchenTicketPrintTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="kitchen_ticket_admin", email="kitchen@example.test", password="test-password",
        )
        self.client.force_login(self.actor)

    def test_delivery_ticket_shows_requested_for_and_bold_customer_name(self):
        requested_for = timezone.now() + timezone.timedelta(hours=2)
        order = Order.objects.create(
            daily_number=970, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Familia Torres", total=100,
            created_by=self.actor, requested_for=requested_for,
        )
        response = self.client.get(reverse("orders:order_kitchen_print", args=(order.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>Entrega:</strong>")
        self.assertContains(response, "<strong>Cliente:</strong> <strong>Familia Torres</strong>")

    def test_pickup_ticket_without_requested_for_hides_the_delivery_field(self):
        order = Order.objects.create(
            daily_number=971, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=50,
            created_by=self.actor,
        )
        response = self.client.get(reverse("orders:order_kitchen_print", args=(order.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<strong>Entrega:</strong>")
        self.assertContains(response, "<strong>Cliente:</strong> <strong>Mostrador</strong>")


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
