from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER

from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product, StockMovement

from print_station.models import PrintStation

from tables.models import DiningTable, TableAccount

from .forms import InternalOrderForm
from .models import Customer, CustomerCreditMovement, CustomerDebt, Order, OrderItem, TerminalCut, TerminalMovement
from .services import (
    add_customer_credit, add_internal_order_package, add_internal_order_product, assign_delivery,
    apply_customer_credit_to_order, change_internal_order_item, change_internal_order_type,
    close_internal_order_capture, create_customer_debt, refund_customer_credit,
    set_cashier_release, settle_selected_debts_from_cashier, transition_order, update_cashier_payment,
    update_delivery_tip, update_internal_package_extras,
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
        self.assertContains(response, "internal-ticket-quick-actions")
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
            "cash_custom_amount": "20", "for_print": "1",
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

    def test_loose_product_is_also_visible_in_breakfast_mode(self):
        session = self.client.session
        session["internal_order_menu_mode"] = "breakfast"
        session.save()

        response = self.client.get(reverse("orders:internal_order_edit", args=(self.order.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-product-name="bolillo"')


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


class AddWaterToPackageTests(TestCase):
    # NOTA TEMPORAL PARA APRENDIZAJE: reproduce el bug reportado en producción
    # ("FOR UPDATE no puede ser aplicado al lado nulable de un outer join", 500 al
    # agregar el agua del día desde Bebidas frías) — necesita correr contra Postgres
    # real (este proyecto usa Postgres tanto en dev como en pruebas) para que la
    # restricción de Postgres realmente se ejerza. Borra esta nota después de leerla.
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="water_upgrade_user")
        self.actor.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        category = Category.objects.create(name="Componentes agua")
        self.component = Product.objects.create(
            category=category, name="Componente agua", price=20,
            component_type=Product.ComponentType.SECOND_COURSE,
            is_sold_individually=False,
        )
        self.water = Product.objects.create(
            category=category, name="Jamaica del día", price=0,
            component_type=Product.ComponentType.DAILY_WATER,
        )
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(
            date=today, status=DailyMenu.Status.PUBLISHED,
            second_course_one=self.component, water_product=self.water,
        )
        self.component_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.component,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=10,
        )
        self.water_stock = DailyProductStock.objects.create(
            date=today, daily_menu=self.menu, product=self.water,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=10,
        )
        self.package, _ = MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={
                "name": "Paquete agua", "price_without_water": 70,
                "price_with_water": 80, "table_refill_price": 10,
            },
        )
        self.order = Order.objects.create(
            daily_number=993, operating_date=today, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=0, created_by=self.actor,
        )
        self.item = add_internal_order_package(
            order=self.order, package=self.package, daily_menu=self.menu, actor=self.actor,
            cleaned_data={
                "first_course": self.component, "second_course": self.component,
                "main_course": self.component, "chicken_piece": "",
                "with_water": False, "tortillas": "no", "bread": False,
                "beans": "no", "quantity": 1, "customization_comment": "",
            },
        )
        self.client.force_login(self.actor)

    def test_adding_daily_water_from_the_catalog_does_not_500(self):
        response = self.client.post(
            reverse("orders:internal_order_product_add", args=(self.order.pk, self.water.pk)),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.item.refresh_from_db()
        self.assertTrue(self.item.with_water)
        self.assertEqual(self.item.water_product, self.water)
        self.assertEqual(self.item.unit_price, self.package.price_with_water)


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


@override_settings(PRINT_AGENT_TOKEN="test-token")
class KitchenCustomPrintStatusTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="custom_print_admin", email="custom_print@example.test",
            password="test-password",
        )
        PrintStation.objects.create(
            name="cocina", printer_available=True, last_heartbeat_at=timezone.now(),
        )
        self.order = Order.objects.create(
            daily_number=994, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=5,
            created_by=self.actor,
        )
        self.item = self.order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Bolillo",
            tortillas=False, beans=False,
            unit_price=5, quantity=1, subtotal=5,
        )
        self.client.force_login(self.actor)

    def test_queuing_a_custom_kitchen_ticket_redirects_with_the_job_id(self):
        response = self.client.post(
            reverse("orders:order_kitchen_custom_print", args=(self.order.pk,)),
            {f"item_{self.item.pk}": "on", f"quantity_{self.item.pk}": "1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"{reverse('orders:order_detail', args=(self.order.pk,))}?printed_job=", response.url)

    def test_order_detail_shows_the_print_status_placeholder_for_the_job(self):
        response = self.client.post(
            reverse("orders:order_kitchen_custom_print", args=(self.order.pk,)),
            {f"item_{self.item.pk}": "on", f"quantity_{self.item.pk}": "1"},
        )
        detail_response = self.client.get(response.url)

        self.assertContains(detail_response, "data-print-job-status")


class DeliveryBoardQuickStatusControlTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="repartos_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.telefonista = get_user_model().objects.create_user(username="repartos_telefonista")
        self.telefonista.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        self.courier = get_user_model().objects.create_user(username="repartos_courier_for_admin_test")
        self.courier.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.order = Order.objects.create(
            daily_number=983, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.READY, customer_name="Cliente reparto", total=80,
            payment_method=Order.PaymentMethod.CARD, delivery_person=self.courier,
        )

    def test_admin_sees_the_full_status_control_on_the_delivery_board(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-delivery-quick-status-form")
        self.assertContains(response, reverse("orders:order_resolve", args=(self.order.pk,)))

    def test_order_taker_also_sees_the_full_status_control(self):
        self.client.force_login(self.telefonista)
        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-delivery-quick-status-form")

    def test_courier_does_not_see_the_full_status_control(self):
        self.client.force_login(self.courier)
        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-delivery-quick-status-form")

    def test_admin_can_advance_status_from_the_delivery_board(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("orders:order_resolve", args=(self.order.pk,)),
            {"action": "dispatch_delivery"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.OUT_FOR_DELIVERY)


class DraftOrderQuickCloseTests(TestCase):
    # NOTA: un pedido "Capturando" (DRAFT) se quedaba sin ninguna acción disponible en
    # el control rápido de estado (Caja/Repartos) — available_order_actions() no sabía
    # nada de ese estado. Esto confirma que ahora sí se puede avanzar, reutilizando la
    # misma validación de close_internal_order_capture (no un atajo que se la salte).
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="draft_close_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.order = Order.objects.create(
            daily_number=984, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=25,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
            created_by=self.admin,
        )
        self.client.force_login(self.admin)

    def test_admin_can_advance_a_complete_draft_via_the_quick_action(self):
        self.order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Bolillo",
            tortillas=False, beans=False, unit_price=25, quantity=1, subtotal=25,
        )
        response = self.client.post(
            reverse("orders:order_resolve", args=(self.order.pk,)),
            {"action": "close_draft"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, Order.Status.DRAFT)

    def test_quick_action_still_blocks_an_empty_draft(self):
        response = self.client.post(
            reverse("orders:order_resolve", args=(self.order.pk,)),
            {"action": "close_draft"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("al menos un producto", response.json()["error"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DRAFT)


class MarkOrderAsUnpaidTests(TestCase):
    # NOTA: antes se exigía Entregado/Recogido para dejar un pedido a cuenta; el
    # desarrollador pidió quitar esa exigencia — cualquier estado es elegible salvo
    # Cancelado. Estas pruebas cubren el cambio de regla, no sólo el caso feliz de antes.
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="unpaid_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.customer = Customer.objects.create(name="Cliente con adeudo")
        self.client.force_login(self.admin)

    def make_order(self, status, daily_number):
        return Order.objects.create(
            daily_number=daily_number, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=status, customer_name=self.customer.name, total=60,
            agenda_customer=self.customer, created_by=self.admin,
        )

    def test_an_order_still_being_prepared_can_now_be_marked_as_unpaid(self):
        order = self.make_order(Order.Status.PREPARING, 985)
        debt = create_customer_debt(order=order, actor=self.admin)
        self.assertEqual(debt.customer_id, self.customer.pk)
        self.assertEqual(debt.original_amount, 60)

    def test_a_canceled_order_still_cannot_be_marked_as_unpaid(self):
        order = self.make_order(Order.Status.CANCELED, 986)
        with self.assertRaisesMessage(ValidationError, "cancelado no puede dejarse a cuenta"):
            create_customer_debt(order=order, actor=self.admin)

    def test_a_delivery_out_for_delivery_no_longer_gets_auto_completed(self):
        order = Order.objects.create(
            daily_number=987, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.OUT_FOR_DELIVERY, customer_name=self.customer.name, total=60,
            agenda_customer=self.customer, created_by=self.admin,
        )
        create_customer_debt(order=order, actor=self.admin)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.OUT_FOR_DELIVERY)

    def test_order_board_item_offers_mark_as_unpaid_from_the_kebab_menu(self):
        order = self.make_order(Order.Status.PREPARING, 988)
        response = self.client.get(reverse("orders:order_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("cashier:order_debt_create", args=(order.pk,)))

    def test_cashier_board_offers_mark_as_unpaid_from_the_kebab_menu(self):
        order = self.make_order(Order.Status.PREPARING, 989)
        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("cashier:order_debt_create", args=(order.pk,)))


class CustomerCreditTests(TestCase):
    # NOTA TEMPORAL PARA APRENDIZAJE: espejo de las pruebas de CustomerDebt, para el
    # saldo a favor (depósitos adelantados que un cliente va consumiendo en varios
    # pedidos). Borra esta nota después de leerla.
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="credit_admin")
        self.actor.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.customer = Customer.objects.create(name="Cliente con depósito", phone="5551112222")
        self.client.force_login(self.actor)

    def make_order(self, *, total, status=Order.Status.DRAFT, credit_applied=0, daily_number=None, order_type=Order.OrderType.PICKUP, **extra):
        return Order.objects.create(
            daily_number=daily_number or (2000 + Order.objects.count()),
            operating_date=timezone.localdate(), order_type=order_type,
            source=Order.Source.INTERNAL, status=status, customer_name=self.customer.name,
            agenda_customer=self.customer, total=total, credit_applied=credit_applied,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
            created_by=self.actor, **extra,
        )

    def test_add_customer_credit_increases_balance_and_logs_a_deposit_movement(self):
        add_customer_credit(
            customer=self.customer, amount="1000", payment_method=Order.PaymentMethod.CASH,
            actor=self.actor, note="Depósito inicial",
        )
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("1000"))
        movement = self.customer.credit_movements.get()
        self.assertEqual(movement.action, CustomerCreditMovement.Action.DEPOSIT)
        self.assertEqual(movement.amount, Decimal("1000"))

    def test_add_customer_credit_rejects_a_zero_or_negative_amount(self):
        with self.assertRaisesMessage(ValidationError, "mayor a cero"):
            add_customer_credit(
                customer=self.customer, amount="0", payment_method=Order.PaymentMethod.CASH, actor=self.actor,
            )

    def test_refund_customer_credit_decreases_balance_and_logs_a_refund_movement(self):
        add_customer_credit(customer=self.customer, amount="1000", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        refund_customer_credit(customer=self.customer, amount="400", actor=self.actor, note="Se le devolvió en efectivo")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("600"))
        self.assertEqual(
            self.customer.credit_movements.filter(action=CustomerCreditMovement.Action.REFUND).get().amount,
            Decimal("400"),
        )

    def test_refund_cannot_exceed_the_available_balance(self):
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        with self.assertRaisesMessage(ValidationError, "no superar el saldo"):
            refund_customer_credit(customer=self.customer, amount="500", actor=self.actor)

    def test_apply_credit_covers_an_order_partially_and_leaves_a_remainder(self):
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=350)
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=350, quantity=1, subtotal=350,
        )
        apply_customer_credit_to_order(order=order, actor=self.actor)
        order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(order.credit_applied, Decimal("200"))
        self.assertEqual(self.customer.credit_balance, Decimal("0"))
        self.assertEqual(order.total - order.credit_applied, Decimal("150"))

    def test_closing_capture_auto_applies_credit_and_skips_the_cash_check_when_fully_covered(self):
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(
            total=200, payment_method=Order.PaymentMethod.CASH, needs_change=True,
        )
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        close_internal_order_capture(order=order, actor=self.actor)
        order.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(order.credit_applied, Decimal("200"))
        self.assertEqual(self.customer.credit_balance, Decimal("300"))
        self.assertNotEqual(order.status, Order.Status.DRAFT)

    def test_marking_unpaid_only_charges_the_amount_not_covered_by_credit(self):
        order = self.make_order(status=Order.Status.PREPARING, total=350, credit_applied=200)
        debt = create_customer_debt(order=order, actor=self.actor)
        self.assertEqual(debt.original_amount, Decimal("150"))

    def test_marking_unpaid_is_blocked_when_credit_fully_covers_the_order(self):
        order = self.make_order(status=Order.Status.PREPARING, total=200, credit_applied=200)
        with self.assertRaisesMessage(ValidationError, "cubierto por completo"):
            create_customer_debt(order=order, actor=self.actor)

    def test_cashier_can_register_a_deposit_by_customer_name(self):
        response = self.client.post(reverse("cashier:credit_deposit"), {
            "customer_query": self.customer.name, "amount": "1000",
            "payment_method": Order.PaymentMethod.CASH, "note": "Depósito del sábado",
        })
        self.assertRedirects(response, f"{reverse('cashier:credit_board')}?customer={self.customer.pk}")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("1000"))

    def test_cashier_can_register_a_deposit_by_picking_a_customer_id(self):
        # NOTA: simula al operador escribiendo en el buscador (customer-picker.js) y
        # haciendo clic en una sugerencia — el formulario manda customer_id en vez de
        # depender de que el nombre escrito coincida exactamente con uno solo.
        another_customer = Customer.objects.create(name="Cliente con depósito extra", phone="5550001111")
        response = self.client.post(reverse("cashier:credit_deposit"), {
            "customer_query": "texto que ya no importa", "customer_id": str(another_customer.pk),
            "amount": "300", "payment_method": Order.PaymentMethod.CASH, "note": "",
        })
        self.assertRedirects(response, f"{reverse('cashier:credit_board')}?customer={another_customer.pk}")
        another_customer.refresh_from_db()
        self.assertEqual(another_customer.credit_balance, Decimal("300"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("0"))

    def test_cashier_can_register_a_refund(self):
        add_customer_credit(customer=self.customer, amount="1000", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        response = self.client.post(
            reverse("cashier:credit_refund", args=(self.customer.pk,)), {"amount": "250", "note": "Se le devolvió"},
        )
        self.assertRedirects(response, f"{reverse('cashier:credit_board')}?customer={self.customer.pk}")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("750"))

    def test_customer_page_shows_the_credit_balance_and_accepts_a_deposit(self):
        response = self.client.post(reverse("orders:customer_edit", args=(self.customer.pk,)), {
            "action": "credit_deposit", "amount": "500",
            "payment_method": Order.PaymentMethod.CASH, "note": "",
        })
        self.assertRedirects(response, reverse("orders:customer_edit", args=(self.customer.pk,)))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.credit_balance, Decimal("500"))
        response = self.client.get(reverse("orders:customer_edit", args=(self.customer.pk,)))
        self.assertContains(response, "$500.00")

    def test_capture_form_warns_about_available_credit(self):
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=350)
        response = self.client.get(reverse("orders:internal_order_edit", args=(order.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "saldo a favor")
        self.assertContains(response, "150.00")

    def test_customer_lookup_reports_the_credit_balance(self):
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        response = self.client.get(reverse("orders:customer_lookup"), {"q": self.customer.name})
        self.assertEqual(response.status_code, 200)
        row = response.json()["customers"][0]
        self.assertEqual(row["credit_balance"], "200.00")

    def test_ticket_json_updates_the_credit_projection_live_as_items_are_added(self):
        # NOTA: reproduce lo que reportó el desarrollador — el aviso de saldo a
        # favor debe reflejar el total actual del ticket sin recargar la página,
        # ni esperar a guardar/cerrar. Verifica el mismo payload que ya usa
        # renderTicket() en el navegador cada vez que se agrega un producto.
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=0)
        category = Category.objects.create(name="Categoría saldo en vivo")
        product = Product.objects.create(category=category, name="Producto saldo en vivo", price=350)

        response = self.client.post(
            reverse("orders:internal_order_product_add", args=(order.pk, product.pk)),
        )
        self.assertEqual(response.status_code, 200)
        credit = response.json()["ticket"]["customer_credit"]
        self.assertEqual(credit["balance"], "200.00")
        self.assertEqual(credit["remaining_after_credit"], "150.00")

    def test_ticket_json_shows_full_coverage_when_credit_covers_the_total(self):
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=0)
        category = Category.objects.create(name="Categoría saldo cubierto")
        product = Product.objects.create(category=category, name="Producto saldo cubierto", price=200)

        response = self.client.post(
            reverse("orders:internal_order_product_add", args=(order.pk, product.pk)),
        )
        credit = response.json()["ticket"]["customer_credit"]
        self.assertEqual(credit["balance"], "500.00")
        self.assertEqual(credit["remaining_after_credit"], "0.00")

    def test_amount_due_and_related_properties_discount_applied_credit(self):
        order = self.make_order(status=Order.Status.PREPARING, total=350, credit_applied=200)
        self.assertEqual(order.amount_due, Decimal("150"))
        order.payment_method = Order.PaymentMethod.CASH
        order.needs_change = True
        order.cash_tendered = Decimal("150")
        self.assertEqual(order.change_required, Decimal("0"))
        self.assertEqual(order.courier_return_amount, Decimal("150"))

    def test_cashier_payment_update_only_requires_cash_for_the_amount_still_due(self):
        # NOTA: antes de este arreglo, esta llamada rechazaba $150 porque los
        # comparaba contra order.total ($350) en vez de order.amount_due ($150) —
        # el bug de Caja que el desarrollador pidió corregir junto con lo demás.
        order = self.make_order(
            status=Order.Status.PREPARING, order_type=Order.OrderType.DELIVERY,
            total=350, credit_applied=200,
        )
        updated = update_cashier_payment(
            order=order, payment_method=Order.PaymentMethod.CASH, cash_amount="150", actor=self.actor,
        )
        self.assertEqual(updated.cash_tendered, Decimal("150"))
        self.assertFalse(updated.needs_change)

    def test_cashier_payment_update_still_rejects_cash_below_the_amount_due(self):
        order = self.make_order(
            status=Order.Status.PREPARING, order_type=Order.OrderType.DELIVERY,
            total=350, credit_applied=200,
        )
        with self.assertRaisesMessage(ValidationError, "no cubre el total"):
            update_cashier_payment(
                order=order, payment_method=Order.PaymentMethod.CASH, cash_amount="100", actor=self.actor,
            )

    def test_order_board_and_cashier_board_show_the_applied_credit(self):
        order = self.make_order(status=Order.Status.PREPARING, total=350, credit_applied=200)
        response = self.client.get(reverse("orders:order_list"))
        self.assertContains(response, "Saldo a favor aplicado: $200.00")
        self.assertContains(response, "Falta cobrar: $150.00")
        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all"})
        self.assertContains(response, "Saldo a favor aplicado: $200.00")

    def test_selecting_an_existing_customer_for_delivery_links_it_before_the_address_is_typed(self):
        # NOTA: reproduce el bug real detrás del reporte del desarrollador — al
        # seleccionar un cliente de la agenda para Entrega a domicilio, antes de
        # este arreglo agenda_customer_id NO se guardaba hasta que también se
        # llenaran calle y número exterior. Como el aviso de saldo a favor (y el
        # de adeudo) depende de agenda_customer_id, no aparecía justo al elegir
        # al cliente, sólo después de completar el domicilio. Verifica que ahora
        # el vínculo se guarda de inmediato, sin domicilio todavía.
        order = Order.objects.create(
            daily_number=2100, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=0,
            created_by=self.actor,
        )
        response = self.client.post(reverse("orders:internal_order_customer_autosave", args=(order.pk,)), {
            "order_type": "delivery", "customer_name": self.customer.name,
            "phone": self.customer.phone, "agenda_customer_id": str(self.customer.pk),
            # street/exterior_number deliberadamente vacíos: el domicilio aún no
            # se ha escrito cuando se elige al cliente.
        })
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.agenda_customer_id, self.customer.pk)

    def test_ticket_json_reports_how_much_credit_would_be_applied_and_left_over(self):
        # NOTA: el desarrollador pidió ver, en vivo, no sólo "cuánto falta cobrar"
        # sino también "cuánto se está aplicando de saldo" y "cuánto le va a quedar
        # de saldo disponible" conforme el ticket cambia.
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=0)
        category = Category.objects.create(name="Categoría saldo detallado")
        product = Product.objects.create(category=category, name="Producto saldo detallado", price=200)

        response = self.client.post(
            reverse("orders:internal_order_product_add", args=(order.pk, product.pk)),
        )
        credit = response.json()["ticket"]["customer_credit"]
        self.assertEqual(credit["balance"], "500.00")
        self.assertEqual(credit["applied"], "200.00")
        self.assertEqual(credit["remaining_balance"], "300.00")
        self.assertEqual(credit["remaining_after_credit"], "0.00")

    def test_internal_order_page_shows_a_partial_coverage_warning_when_credit_falls_short(self):
        add_customer_credit(customer=self.customer, amount="200", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=350)
        response = self.client.get(reverse("orders:internal_order_edit", args=(order.pk,)))
        self.assertContains(response, "customer-credit-notice is-partial")
        self.assertContains(response, "se hará un ajuste en el cobro por $150.00")

    def test_internal_order_page_has_no_warning_when_credit_fully_covers_and_leaves_a_balance(self):
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=200)
        response = self.client.get(reverse("orders:internal_order_edit", args=(order.pk,)))
        self.assertNotContains(response, "is-partial")
        self.assertContains(response, "le quedarán $300.00 de saldo a favor para después")

    def test_order_boards_and_delivery_board_show_the_customers_pending_debt(self):
        # NOTA: el desarrollador pidió que el adeudo pendiente ("pedidos no pagados")
        # se vea, igual que el saldo a favor, en Pedidos, Caja y también en Repartos —
        # sin importar a qué otro pedido pertenezca ese adeudo.
        debt_order = self.make_order(total=300, status=Order.Status.DELIVERED, daily_number=2200)
        create_customer_debt(order=debt_order, actor=self.actor)
        self.make_order(
            total=150, status=Order.Status.PREPARING, daily_number=2201,
            order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10",
        )

        response = self.client.get(reverse("orders:order_list"))
        self.assertContains(response, "Adeudo pendiente: $300.00 en 1 pedido(s)")

        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all"})
        self.assertContains(response, "Adeudo pendiente: $300.00 en 1 pedido(s)")

        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertContains(response, "Adeudo pendiente: $300.00 en 1 pedido(s)")

    def test_ticket_json_reports_the_pending_debt_and_its_projected_total_live(self):
        # NOTA: el desarrollador pidió el espejo de saldo a favor, pero para "saldo
        # en contra" — mientras se captura un pedido NUEVO, mostrar cuánto debe ya
        # el cliente y cuánto deberá en total si este pedido nuevo tampoco se paga,
        # actualizándose conforme se agregan productos (sin recargar ni cerrar).
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2300)
        create_customer_debt(order=debt_order, actor=self.actor)
        order = self.make_order(total=0, daily_number=2301)
        category = Category.objects.create(name="Categoría saldo en contra")
        product = Product.objects.create(category=category, name="Producto saldo en contra", price=80)

        response = self.client.post(
            reverse("orders:internal_order_product_add", args=(order.pk, product.pk)),
        )
        debt = response.json()["ticket"]["customer_debt"]
        self.assertEqual(debt["balance"], "100.00")
        self.assertEqual(debt["count"], 1)
        self.assertEqual(debt["projected_total"], "180.00")
        self.assertEqual(debt["orders"][0]["id"], debt_order.pk)
        self.assertEqual(debt["orders"][0]["balance"], "100.00")

    def test_internal_order_page_shows_the_pending_debt_with_a_link_to_the_unpaid_order(self):
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2310)
        create_customer_debt(order=debt_order, actor=self.actor)
        order = self.make_order(total=50, daily_number=2311)

        response = self.client.get(reverse("orders:internal_order_edit", args=(order.pk,)))
        self.assertContains(response, "Este cliente debe $100.00 en 1 pedido(s) anterior(es).")
        self.assertContains(response, "deberá $150.00 en total")
        self.assertContains(response, reverse("orders:internal_order_edit", args=(debt_order.pk,)))

    def test_customer_lookup_reports_the_open_debts_with_their_order_links(self):
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2320)
        create_customer_debt(order=debt_order, actor=self.actor)

        response = self.client.get(reverse("orders:customer_lookup"), {"q": self.customer.name})
        row = response.json()["customers"][0]
        self.assertEqual(row["outstanding_balance"], "100.00")
        self.assertEqual(row["open_debts"][0]["id"], debt_order.pk)
        self.assertEqual(row["open_debts"][0]["url"], reverse("orders:internal_order_edit", args=(debt_order.pk,)))

    def test_settle_selected_debts_pays_the_chosen_orders_oldest_first(self):
        # NOTA: el desarrollador confirmó que, cuando el monto no alcanza para todo
        # lo seleccionado, se abona del adeudo más antiguo al más reciente.
        older_debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2400)
        older_debt = create_customer_debt(order=older_debt_order, actor=self.actor)
        older_debt.created_at = timezone.now() - timedelta(days=2)
        older_debt.save(update_fields=("created_at",))
        newer_debt_order = self.make_order(total=60, status=Order.Status.DELIVERED, daily_number=2401)
        newer_debt = create_customer_debt(order=newer_debt_order, actor=self.actor)

        settle_selected_debts_from_cashier(
            customer=self.customer, debt_ids=[older_debt.pk, newer_debt.pk], amount="120",
            payment_method=Order.PaymentMethod.CASH, actor=self.actor,
        )
        older_debt.refresh_from_db()
        newer_debt.refresh_from_db()
        self.assertEqual(older_debt.status, CustomerDebt.Status.PAID)
        self.assertEqual(older_debt.balance, Decimal("0"))
        self.assertEqual(newer_debt.balance, Decimal("40"))
        self.assertEqual(newer_debt.status, CustomerDebt.Status.PARTIAL)

    def test_settle_selected_debts_rejects_an_amount_above_what_was_selected(self):
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2410)
        debt = create_customer_debt(order=debt_order, actor=self.actor)
        with self.assertRaisesMessage(ValidationError, "no puede superar lo seleccionado"):
            settle_selected_debts_from_cashier(
                customer=self.customer, debt_ids=[debt.pk], amount="150",
                payment_method=Order.PaymentMethod.CASH, actor=self.actor,
            )

    def test_cashier_board_shows_a_form_to_settle_the_customers_pending_debt(self):
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2420)
        create_customer_debt(order=debt_order, actor=self.actor)
        new_order = self.make_order(total=50, status=Order.Status.PREPARING, daily_number=2421)

        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all"})
        self.assertContains(response, "Debe $100.00 en 1 pedido(s) anterior(es)")
        self.assertContains(response, reverse("cashier:settle_debts", args=(new_order.pk,)))

    def test_credit_board_shows_a_running_balance_ledger_for_the_selected_customer(self):
        # NOTA: el desarrollador pidió ver, en el historial de saldo a favor, el
        # balance corrido — con cuánto empezó cada movimiento y con cuánto quedó —
        # no sólo la lista de movimientos sueltos que ya había.
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=200)
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        apply_customer_credit_to_order(order=order, actor=self.actor)
        refund_customer_credit(customer=self.customer, amount="100", actor=self.actor)

        response = self.client.get(reverse("cashier:credit_board"), {"customer": self.customer.pk})
        movements = list(response.context["movements"])
        # El más reciente primero (igual que antes); balance_before/after arman el
        # balance corrido en orden cronológico aunque se muestren al revés.
        self.assertEqual(movements[2].action, CustomerCreditMovement.Action.DEPOSIT)
        self.assertEqual(movements[2].balance_before, Decimal("0"))
        self.assertEqual(movements[2].balance_after, Decimal("500"))
        self.assertEqual(movements[1].action, CustomerCreditMovement.Action.REDEMPTION)
        self.assertEqual(movements[1].balance_before, Decimal("500"))
        self.assertEqual(movements[1].balance_after, Decimal("300"))
        self.assertEqual(movements[0].action, CustomerCreditMovement.Action.REFUND)
        self.assertEqual(movements[0].balance_before, Decimal("300"))
        self.assertEqual(movements[0].balance_after, Decimal("200"))
        self.assertContains(response, "Saldo antes")
        self.assertContains(response, "Saldo después")

    def test_cashier_can_settle_a_customers_debt_from_the_new_orders_payment_panel(self):
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2430)
        debt = create_customer_debt(order=debt_order, actor=self.actor)
        new_order = self.make_order(total=50, status=Order.Status.PREPARING, daily_number=2431)

        response = self.client.post(reverse("cashier:settle_debts", args=(new_order.pk,)), {
            "debt_ids": [str(debt.pk)], "amount": "100", "payment_method": Order.PaymentMethod.CASH,
        })
        self.assertEqual(response.status_code, 302)
        debt.refresh_from_db()
        self.assertEqual(debt.status, CustomerDebt.Status.PAID)

    def test_close_internal_order_capture_auto_assigns_credit_when_it_fully_covers_a_delivery_order(self):
        # NOTA: el desarrollador pidió que, cuando el saldo a favor cubre el pedido
        # por completo, ya no tenga sentido elegir Efectivo/Terminal/Transferencia —
        # el sistema asigna PaymentMethod.CREDIT solo, sin bloquear el cierre.
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=200, order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10")
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        close_internal_order_capture(order=order, actor=self.actor)
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CREDIT)
        self.assertEqual(order.credit_applied, Decimal("200"))
        self.assertNotEqual(order.status, Order.Status.DRAFT)

    def test_close_internal_order_capture_still_requires_a_payment_method_when_credit_falls_short(self):
        add_customer_credit(customer=self.customer, amount="100", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=200, order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10")
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        with self.assertRaisesMessage(ValidationError, "Selecciona la forma de pago"):
            close_internal_order_capture(order=order, actor=self.actor)

    def test_close_internal_order_capture_does_not_override_an_explicit_payment_method(self):
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(
            total=200, order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10",
            payment_method=Order.PaymentMethod.CARD,
        )
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        close_internal_order_capture(order=order, actor=self.actor)
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CARD)

    def test_internal_order_form_skips_the_payment_method_requirement_when_credit_covers_the_total(self):
        form = InternalOrderForm({
            "order_type": Order.OrderType.DELIVERY, "customer_name": "Cliente con saldo",
            "requested_date": timezone.localdate().isoformat(), "requested_time": "13:00",
            "street": "Calle 1", "exterior_number": "10", "payment_method": "",
        }, order_total=200, closing=True, available_credit=Decimal("500"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_internal_order_form_still_requires_a_payment_method_when_credit_falls_short(self):
        form = InternalOrderForm({
            "order_type": Order.OrderType.DELIVERY, "customer_name": "Cliente con saldo",
            "requested_date": timezone.localdate().isoformat(), "requested_time": "13:00",
            "street": "Calle 1", "exterior_number": "10", "payment_method": "",
        }, order_total=200, closing=True, available_credit=Decimal("100"))
        self.assertFalse(form.is_valid())
        self.assertIn("payment_method", form.errors)

    def test_cashier_board_shows_paid_by_credit_instead_of_payment_buttons(self):
        self.make_order(
            status=Order.Status.PREPARING, total=200, credit_applied=200,
            payment_method=Order.PaymentMethod.CREDIT,
        )
        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all"})
        self.assertContains(response, "Pagado con saldo a favor")
        self.assertContains(response, "$200.00 aplicado")

    def test_assignable_payment_method_choices_exclude_credit(self):
        from orders.views import ASSIGNABLE_PAYMENT_METHOD_CHOICES
        self.assertNotIn(
            Order.PaymentMethod.CREDIT, [value for value, _ in ASSIGNABLE_PAYMENT_METHOD_CHOICES],
        )

    def test_payment_print_shows_the_credit_deduction_detail(self):
        order = self.make_order(
            status=Order.Status.PREPARING, total=200, credit_applied=200,
            payment_method=Order.PaymentMethod.CREDIT,
        )
        response = self.client.get(reverse("orders:order_payment_print", args=(order.pk,)))
        self.assertContains(response, "Saldo a favor descontado: $200.00")
        self.assertContains(response, "Saldo a favor")

    def test_no_pago_button_is_marked_to_skip_the_ajax_status_handler(self):
        # NOTA: bug real reportado — el formulario "No pagó" en Pedidos caía dentro
        # del manejador genérico de AJAX de order-list.js (que espera JSON), y como
        # cashier_order_debt_create responde con una redirección normal, el
        # navegador mostraba "No se pudo cambiar el estado" aunque el adeudo SÍ se
        # hubiera creado. order-list.js ya excluía data-debt-create-form de ese
        # manejador, pero la plantilla nunca lo traía. Verifica que ahora sí.
        order = self.make_order(status=Order.Status.PREPARING, total=100)
        response = self.client.get(reverse("orders:order_list"))
        self.assertContains(response, "data-debt-create-form")

    def test_debt_settle_checkboxes_and_amount_are_unchecked_by_default(self):
        # NOTA: el desarrollador pidió que nada venga premarcado en el panel de
        # "Debe $X..." de Caja — el admin debe marcar a propósito qué adeudo(s)
        # cobrar; antes todas las casillas venían marcadas y el monto ya traía la
        # suma completa, lo que se sentía como que "ya se iba a cobrar todo" sin
        # que nadie lo pidiera.
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2440)
        create_customer_debt(order=debt_order, actor=self.actor)
        new_order = self.make_order(total=50, status=Order.Status.PREPARING, daily_number=2441)

        response = self.client.get(reverse("cashier:cashier_board"), {"scope": "all", "q": "2441"})
        self.assertContains(response, 'value="0.00" data-debt-settle-amount')
        self.assertNotIn(b"checked data-debt-balance", response.content)


class CashierToolsNavigationTests(TestCase):
    # NOTA: el desarrollador pidió que las 7 páginas de Caja (Caja, Cuentas por
    # cobrar, Saldos a favor, Corte de terminales, Cambios pendientes, Reporte de
    # propinas, Corte de bebidas calientes) compartan la misma barra "Herramientas"
    # — desde cualquiera de ellas se puede saltar a cualquier otra, sin importar en
    # cuál estés. Telefonista sólo entra a Cuentas por cobrar y Saldos a favor, así
    # que su barra sólo debe ofrecer esas dos.
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="nav_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.telefonista = get_user_model().objects.create_user(username="nav_telefonista")
        self.telefonista.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])

    def test_every_cashier_page_toolbar_links_to_the_other_sections(self):
        # NOTA: cada aserción busca ">Etiqueta<" (el enlace real ya renderizado),
        # no sólo la palabra suelta — el include trae una nota explicativa que
        # menciona las 7 secciones por nombre, y un assertContains simple daría
        # un falso positivo con esa nota aunque el enlace real no estuviera.
        self.client.force_login(self.admin)
        pages = {
            "cashier:cashier_board": [
                "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Reporte de propinas", "Corte de bebidas calientes",
            ],
            "cashier:debt_board": [
                "Caja", "Saldos a favor", "Corte de terminales", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Registrar un pedido que no pagó",
            ],
            "cashier:credit_board": [
                "Caja", "Cuentas por cobrar", "Corte de terminales", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Registrar un pedido que no pagó",
            ],
            "cashier:terminal_board": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Registrar un pedido que no pagó",
            ],
            "cashier:change_board": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Reporte de propinas", "Corte de bebidas calientes", "Registrar un pedido que no pagó",
            ],
            "cashier:tip_report": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Corte de bebidas calientes", "Registrar un pedido que no pagó",
            ],
            "cashier:coffee_report": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Reporte de propinas", "Registrar un pedido que no pagó",
            ],
        }
        for url_name, expected_labels in pages.items():
            response = self.client.get(reverse(url_name))
            for label in expected_labels:
                self.assertContains(response, f">{label}<", msg_prefix=f"{url_name} -> falta enlace a {label}")

    def test_order_taker_only_sees_the_two_sections_it_can_access(self):
        self.client.force_login(self.telefonista)
        response = self.client.get(reverse("cashier:debt_board"))
        self.assertContains(response, ">Saldos a favor<")
        self.assertNotContains(response, ">Caja<")
        self.assertNotContains(response, ">Corte de terminales<")
        self.assertNotContains(response, ">Registrar un pedido que no pagó<")

    def test_no_pago_toolbar_link_points_to_the_cashier_quick_form(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("cashier:tip_report"))
        self.assertContains(response, f'{reverse("cashier:cashier_board")}#registrar-no-pagado')
