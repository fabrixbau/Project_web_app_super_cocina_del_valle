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

from tables.models import DiningTable, TableAccount, TableAccountItem
from tables.services import add_product_to_table, open_table_account

from .forms import InternalOrderForm
from .models import CashRegisterCut, CashRegisterExpense, Customer, CustomerCreditMovement, CustomerDebt, Order, OrderItem, TerminalCut, TerminalMovement
from .services import (
    add_customer_credit, add_internal_order_package, add_internal_order_product, assign_delivery,
    apply_customer_credit_to_order, change_internal_order_item, change_internal_order_type,
    close_internal_order_capture, create_customer_debt, refund_customer_credit,
    set_cashier_release, settle_selected_debts_from_cashier, transfer_order_to_table,
    transfer_table_to_order, transition_order, update_cashier_payment,
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

    def test_courier_cannot_assign_orders(self):
        assign_response = self.client.post(
            reverse("deliveries:delivery_assign", args=(self.order.pk,)),
            {"delivery_person": self.courier.pk},
        )
        self.assertEqual(assign_response.status_code, 403)

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

    def test_courier_sees_complete_action_for_assigned_cash_delivery(self):
        response = self.client.get(reverse("deliveries:delivery_board"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("deliveries:delivery_complete", args=(self.order.pk,)),
        )
        self.assertContains(response, "Marcar como entregado")

    def test_courier_orders_pending_actions_by_cashier_release_and_delivered_last(self):
        now = timezone.now()
        first_pending = Order.objects.create(
            daily_number=975, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.OUT_FOR_DELIVERY, customer_name="Primero liberado",
            total=90, payment_method=Order.PaymentMethod.CARD,
            delivery_person=self.courier,
        )
        delivered = Order.objects.create(
            daily_number=974, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Ya entregado",
            total=90, payment_method=Order.PaymentMethod.TRANSFER,
            delivery_person=self.courier,
        )
        Order.objects.filter(pk=first_pending.pk).update(
            cashier_released_at=now - timedelta(minutes=10),
        )
        Order.objects.filter(pk=self.order.pk).update(cashier_released_at=now)
        Order.objects.filter(pk=delivered.pk).update(
            cashier_released_at=now - timedelta(minutes=20),
        )

        response = self.client.get(reverse("deliveries:delivery_board"))

        self.assertEqual(response.status_code, 200)
        ordered_ids = [order.pk for order in response.context["delivery_orders"]]
        self.assertLess(ordered_ids.index(first_pending.pk), ordered_ids.index(self.order.pk))
        self.assertLess(ordered_ids.index(self.order.pk), ordered_ids.index(delivered.pk))

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

    def test_courier_can_complete_own_delivery_with_any_payment_method(self):
        for payment_method in (
            Order.PaymentMethod.CASH,
            Order.PaymentMethod.CARD,
            Order.PaymentMethod.TRANSFER,
        ):
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
                if payment_method == Order.PaymentMethod.CASH:
                    self.assertFalse(order.cash_settlement_confirmed)

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

    def test_clicking_the_selected_courier_can_unassign_it_from_cashier(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("deliveries:delivery_assign", args=(self.order.pk,)),
            {"delivery_person": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["delivery_person_id"], "")
        self.assertEqual(response.json()["delivery_person_name"], "Sin asignar")
        self.order.refresh_from_db()
        self.movement.refresh_from_db()
        self.assertIsNone(self.order.delivery_person_id)
        self.assertIsNone(self.order.delivery_assigned_by_id)
        self.assertIsNone(self.order.delivery_assigned_at)
        self.assertIsNone(self.order.delivery_tip_recipient_id)
        self.assertIsNone(self.movement.tip_recipient_id)

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

    def test_filters_and_cut_controls_share_the_row_before_color_palette(self):
        response = self.client.get(
            reverse("cashier:terminal_board"), {"provider": TerminalCut.Provider.TRANSFER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="terminal-controls-row"')
        self.assertContains(response, "data-terminal-filters", count=1)
        html = response.content.decode()
        self.assertLess(html.index("terminal-controls-row"), html.index("terminal-color-palette"))

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

    def test_candidates_with_no_tip_are_excluded_from_the_link_list(self):
        # NOTA: el desarrollador pidió que este corte, hecho para conciliar
        # propinas, deje de mostrar como "vinculable" un ticket que no dejó
        # ninguna propina — no hay nada que conciliar ahí.
        no_tip_order = self.make_delivery_order(
            daily_number=921, payment_method=Order.PaymentMethod.TRANSFER,
            status=Order.Status.DELIVERED,
        )
        tipped_order = self.make_delivery_order(
            daily_number=922, payment_method=Order.PaymentMethod.TRANSFER,
            status=Order.Status.DELIVERED,
        )
        tipped_order.delivery_tip_amount = Decimal("20")
        tipped_order.save(update_fields=("delivery_tip_amount",))
        no_tip_table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.TRANSFER)
        tipped_table = self.make_closed_table(payment_method=TableAccount.PaymentMethod.TRANSFER)
        tipped_table.tip_amount = Decimal("15")
        tipped_table.save(update_fields=("tip_amount",))

        response = self.client.get(f"{reverse('cashier:terminal_board')}?provider=transfer")
        candidate_values = {candidate["value"] for candidate in response.context["link_candidates"]}
        self.assertIn(f"order:{tipped_order.pk}", candidate_values)
        self.assertIn(f"table:{tipped_table.pk}", candidate_values)
        self.assertNotIn(f"order:{no_tip_order.pk}", candidate_values)
        self.assertNotIn(f"table:{no_tip_table.pk}", candidate_values)

    def test_row_classification_color_is_saved_changed_and_removed(self):
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
        )
        response = self.client.post(reverse("cashier:terminal_movement_save"), {
            "cut_id": cut.pk,
            "total_amount": "125.00",
            "tip_amount": "5.00",
            "linked_record": "",
            "terminal_name_reference": "Referencia manual",
            "classification_color": "hsl(12 68% 48%)",
        })
        self.assertEqual(response.status_code, 200)
        movement = TerminalMovement.objects.get()
        self.assertEqual(movement.classification_color, "hsl(12 68% 48%)")
        self.assertEqual(response.json()["movement"]["classification_color"], "hsl(12 68% 48%)")

        response = self.client.post(reverse("cashier:terminal_movement_save"), {
            "cut_id": cut.pk,
            "movement_id": movement.pk,
            "total_amount": "125.00",
            "tip_amount": "5.00",
            "linked_record": "",
            "terminal_name_reference": "Referencia manual",
            "classification_color": "",
        })
        self.assertEqual(response.status_code, 200)
        movement.refresh_from_db()
        self.assertEqual(movement.classification_color, "")

    def test_invalid_row_classification_color_is_rejected(self):
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
        )
        response = self.client.post(reverse("cashier:terminal_movement_save"), {
            "cut_id": cut.pk, "total_amount": "100.00", "tip_amount": "0",
            "linked_record": "", "classification_color": "red; background:url(x)",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TerminalMovement.objects.exists())

    def test_terminal_movements_can_be_reordered_and_keep_the_new_order(self):
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
        )
        movements = [
            TerminalMovement.objects.create(
                cut=cut, total_amount=amount, display_position=index,
                created_by=self.admin,
            )
            for index, amount in enumerate((100, 200, 300), start=1)
        ]

        response = self.client.post(reverse("cashier:terminal_movement_reorder"), {
            "cut_id": cut.pk,
            "movement_ids[]": [movements[2].pk, movements[0].pk, movements[1].pk],
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(cut.movements.values_list("pk", flat=True)),
            [movements[2].pk, movements[0].pk, movements[1].pk],
        )
        board = self.client.get(
            reverse("cashier:terminal_board"), {"provider": TerminalCut.Provider.TRANSFER},
        )
        self.assertEqual(
            [movement.pk for movement in board.context["movements"]],
            [movements[2].pk, movements[0].pk, movements[1].pk],
        )

    def test_new_terminal_movement_is_inserted_above_previous_records(self):
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
        )
        previous = TerminalMovement.objects.create(
            cut=cut, total_amount=80, display_position=1, created_by=self.admin,
        )

        response = self.client.post(reverse("cashier:terminal_movement_save"), {
            "cut_id": cut.pk, "total_amount": "120.00", "tip_amount": "0",
            "linked_record": "", "terminal_name_reference": "Nuevo",
        })

        self.assertEqual(response.status_code, 200)
        new_movement = TerminalMovement.objects.get(pk=response.json()["movement"]["id"])
        self.assertEqual(
            list(cut.movements.values_list("pk", flat=True)),
            [new_movement.pk, previous.pk],
        )

    def test_closed_terminal_cut_cannot_be_reordered(self):
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
            status=TerminalCut.Status.CLOSED,
        )
        movement = TerminalMovement.objects.create(
            cut=cut, total_amount=100, created_by=self.admin,
        )

        response = self.client.post(reverse("cashier:terminal_movement_reorder"), {
            "cut_id": cut.pk, "movement_ids[]": [movement.pk],
        })

        self.assertEqual(response.status_code, 400)

    def test_daily_palette_contains_active_staff_and_distinct_manual_references(self):
        courier = get_user_model().objects.create_user(username="terminal_courier")
        courier.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        cut = TerminalCut.objects.create(
            operating_date=self.today, provider=TerminalCut.Provider.TRANSFER,
        )
        TerminalMovement.objects.create(
            cut=cut, total_amount=100, terminal_name_reference="Manual uno", created_by=self.admin,
        )
        TerminalMovement.objects.create(
            cut=cut, total_amount=80, terminal_name_reference="manual UNO", created_by=self.admin,
        )
        other_cut = TerminalCut.objects.create(
            operating_date=self.today - timedelta(days=1), provider=TerminalCut.Provider.TRANSFER,
        )
        TerminalMovement.objects.create(
            cut=other_cut, total_amount=70, terminal_name_reference="No debe aparecer", created_by=self.admin,
        )

        response = self.client.get(f"{reverse('cashier:terminal_board')}?provider=transfer")
        self.assertEqual(response.status_code, 200)
        labels = [item["label"] for item in response.context["color_palette"]]
        self.assertEqual(labels, [courier.username, self.waiter.username, "Manual uno"])
        self.assertEqual(len({item["color"] for item in response.context["color_palette"]}), 3)


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
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PREPARING)
        self.assertEqual(self.pickup_stock.available_quantity, 1)
        change_internal_order_item(order=self.order, item=item, action="increase", actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, 0)
        change_internal_order_item(order=self.order, item=item, action="increase", actor=self.actor)
        self.assertEqual(self.pickup_stock.available_quantity, -1)
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
        self.assertContains(response, 'class="change-overview"')
        self.assertContains(response, 'class="change-summary-grid"')
        self.assertContains(response, 'class="card change-person-summary"')

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
        self.menu = DailyMenu.objects.create(date=today, status=DailyMenu.Status.PUBLISHED)
        self.menu.set_stews([self.chicken])
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


class ExactFolioBoardSearchTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="exact_folio_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.courier = get_user_model().objects.create_user(username="exact_folio_courier")
        self.courier.groups.add(Group.objects.get_or_create(name=DELIVERY)[0])
        self.old_date = timezone.localdate() - timedelta(days=40)
        self.order = Order.objects.create(
            daily_number=731, operating_date=self.old_date,
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.DELIVERED, customer_name="Folio fuera de filtros",
            total=120, payment_method=Order.PaymentMethod.TRANSFER,
            delivery_person=self.courier, cashier_released_at=timezone.now(),
        )
        self.client.force_login(self.admin)

    def test_cashier_full_folio_ignores_date_scope_type_courier_and_payment_filters(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("cashier:cashier_board"), {
            "q": self.order.formatted_number,
            "date_from": today,
            "date_to": today,
            "scope": "active",
            "type": Order.OrderType.PICKUP,
            "delivery_person": "unassigned",
            "payment_method": Order.PaymentMethod.CASH,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.formatted_number)
        self.assertContains(response, self.order.customer_name)

    def test_delivery_full_folio_ignores_date_status_and_courier_filters(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("deliveries:delivery_board"), {
            "q": f"#{self.order.formatted_number}",
            "date_from": today,
            "date_to": today,
            "status": Order.Status.READY,
            "delivery_person": "unassigned",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.formatted_number)
        self.assertContains(response, self.order.customer_name)

    def test_order_board_full_folio_ignores_date_scope_status_and_type_filters(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("orders:order_list"), {
            "q": self.order.formatted_number,
            "date_from": today,
            "date_to": today,
            "scope": "active",
            "status": Order.Status.READY,
            "order_type": Order.OrderType.PICKUP,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.formatted_number)
        self.assertContains(response, self.order.customer_name)

    def test_change_board_full_folio_ignores_every_other_filter(self):
        self.order.payment_method = Order.PaymentMethod.CASH
        self.order.cash_tendered = 200
        self.order.needs_change = True
        self.order.save(update_fields=("payment_method", "cash_tendered", "needs_change"))
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("cashier:change_board"), {
            "q": self.order.formatted_number,
            "from": today,
            "to": today,
            "settlement": "pending",
            "order_type": Order.OrderType.PICKUP,
            "payment_method": "cash_change",
            "status": Order.Status.READY,
            "delivery_person": "999999",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.formatted_number)
        self.assertContains(response, self.order.customer_name)
        self.assertContains(response, "data-settlement-form")

    def test_change_board_customer_suggestions_only_include_orders_from_today(self):
        today_order = Order.objects.create(
            daily_number=732, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL,
            status=Order.Status.READY, customer_name="Alicia Coincidente", total=90,
        )

        response = self.client.get(reverse("cashier:change_board"))

        options = response.context["today_search_options"]
        self.assertIn(
            {"folio": today_order.formatted_number, "customer": today_order.customer_name},
            options,
        )
        self.assertNotIn(
            {"folio": self.order.formatted_number, "customer": self.order.customer_name},
            options,
        )
        self.assertContains(response, 'id="change-order-search-options"')

    def test_short_consecutive_does_not_bypass_cashier_filters(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(reverse("cashier:cashier_board"), {
            "q": str(self.order.daily_number),
            "date_from": today,
            "date_to": today,
            "scope": "all",
        })

        self.assertNotContains(response, self.order.customer_name)

    def test_order_and_cashier_autocomplete_defaults_to_today(self):
        today_order = Order.objects.create(
            daily_number=733, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.PREPARING, customer_name="Cliente de hoy", total=75,
        )

        for view_name in ("orders:order_list", "cashier:cashier_board"):
            with self.subTest(view=view_name):
                response = self.client.get(reverse(view_name))
                self.assertContains(response, "data-click-toggle-select")
                self.assertIn(
                    {"folio": today_order.formatted_number, "customer": today_order.customer_name},
                    response.context["order_search_options"],
                )
                self.assertNotIn(
                    {"folio": self.order.formatted_number, "customer": self.order.customer_name},
                    response.context["order_search_options"],
                )

    def test_order_and_cashier_autocomplete_uses_selected_date_range(self):
        params = {
            "date_from": self.old_date.isoformat(),
            "date_to": self.old_date.isoformat(),
        }

        for view_name in ("orders:order_list", "cashier:cashier_board"):
            with self.subTest(view=view_name):
                response = self.client.get(reverse(view_name), params)
                self.assertIn(
                    {"folio": self.order.formatted_number, "customer": self.order.customer_name},
                    response.context["order_search_options"],
                )


class OperationalBoardOrderingTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="board_order_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.client.force_login(self.admin)
        now = timezone.now()
        self.normal_old = self._make_order(801, "Normal anterior")
        self.normal_new = self._make_order(802, "Normal posterior")
        self.scheduled_late = self._make_order(803, "Programado tarde", now + timedelta(hours=4))
        self.scheduled_early = self._make_order(804, "Programado temprano", now + timedelta(hours=2))
        Order.objects.filter(pk=self.normal_old.pk).update(created_at=now - timedelta(minutes=20))
        Order.objects.filter(pk=self.normal_new.pk).update(created_at=now - timedelta(minutes=10))
        Order.objects.filter(pk__in=(self.scheduled_late.pk, self.scheduled_early.pk)).update(
            created_at=now - timedelta(minutes=5),
        )

    def _make_order(self, number, name, requested_for=None):
        return Order.objects.create(
            daily_number=number,
            operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY,
            source=Order.Source.INTERNAL,
            status=Order.Status.PREPARING,
            customer_name=name,
            total=100,
            requested_for=requested_for,
        )

    def _delivery_ids(self, response):
        return [order.pk for order in response.context["delivery_orders"]]

    def test_order_board_lists_normal_by_creation_then_scheduled_by_requested_time(self):
        response = self.client.get(reverse("orders:order_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._delivery_ids(response), [
            self.normal_old.pk,
            self.normal_new.pk,
            self.scheduled_early.pk,
            self.scheduled_late.pk,
        ])

    def test_cashier_board_uses_the_same_operational_order(self):
        response = self.client.get(reverse("cashier:cashier_board"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._delivery_ids(response), [
            self.normal_old.pk,
            self.normal_new.pk,
            self.scheduled_early.pk,
            self.scheduled_late.pk,
        ])


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


class InternalOrderAutomaticPreparingTests(TestCase):
    def setUp(self):
        self.operator = get_user_model().objects.create_user(username="automatic_preparing_operator")
        self.operator.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        self.client.force_login(self.operator)
        self.order = Order.objects.create(
            daily_number=972, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Mostrador", total=0,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
            created_by=self.operator,
        )

    def autosave(self, customer_name):
        return self.client.post(
            reverse("orders:internal_order_customer_autosave", args=(self.order.pk,)),
            {"order_type": Order.OrderType.PICKUP, "customer_name": customer_name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_customer_data_promotes_draft_even_without_products(self):
        response = self.autosave("Cliente sin productos")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PREPARING)
        self.assertFalse(self.order.items.exists())

        board = self.client.get(reverse("orders:order_list"))
        self.assertContains(board, "Cliente sin productos")
        self.assertContains(board, "Sin productos")
        self.assertContains(board, "order-board-summary is-empty")
        self.assertNotContains(board, "Marcar como listo")

    def test_untouched_pickup_default_does_not_promote_the_empty_draft(self):
        response = self.autosave("Mostrador")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DRAFT)

    def test_preparing_order_without_products_cannot_be_marked_ready(self):
        self.order.status = Order.Status.PREPARING
        self.order.customer_name = "Cliente sin productos"
        self.order.save(update_fields=("status", "customer_name"))

        with self.assertRaisesMessage(ValidationError, "Agrega al menos un producto"):
            transition_order(order=self.order, action="mark_ready", actor=self.operator)


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

    def test_close_capture_endpoint_returns_json_and_closes_when_called_via_ajax(self):
        # NOTA: el desarrollador pidió que "Imprimir cobro" pueda cerrar la
        # captura primero (por fetch) para que el ticket refleje datos reales.
        # Este endpoint ya existía sólo con redirección; ahora también responde
        # en JSON cuando se llama por AJAX.
        order = self.make_order(total=200)
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        response = self.client.post(
            reverse("orders:internal_order_close_capture", args=(order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.Status.DRAFT)

    def test_close_capture_endpoint_returns_json_error_when_delivery_is_missing_a_payment_method(self):
        order = self.make_order(total=200, order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10")
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        response = self.client.post(
            reverse("orders:internal_order_close_capture", args=(order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecciona la forma de pago", response.json()["error"])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DRAFT)

    def test_close_capture_endpoint_closes_a_delivery_order_fully_covered_by_credit_via_ajax(self):
        add_customer_credit(customer=self.customer, amount="500", payment_method=Order.PaymentMethod.CASH, actor=self.actor)
        order = self.make_order(total=200, order_type=Order.OrderType.DELIVERY, street="Calle 1", exterior_number="10")
        order.items.create(
            item_type=OrderItem.ItemType.PRODUCT, product_name_snapshot="Comida",
            tortillas=False, beans=False, unit_price=200, quantity=1, subtotal=200,
        )
        response = self.client.post(
            reverse("orders:internal_order_close_capture", args=(order.pk,)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.json(), {"ok": True})
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CREDIT)
        self.assertEqual(order.credit_applied, Decimal("200"))

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

    def test_payment_print_shows_pending_debt_from_other_orders(self):
        # NOTA: el desarrollador pidió que el ticket de cobro siempre avise si el
        # cliente ya debe de pedidos anteriores, sin importar cómo se esté
        # cobrando el pedido actual (es informativo, como el aviso ya visible
        # durante la captura y en los tableros).
        debt_order = self.make_order(total=100, status=Order.Status.DELIVERED, daily_number=2450)
        create_customer_debt(order=debt_order, actor=self.actor)
        new_order = self.make_order(status=Order.Status.PREPARING, total=80, daily_number=2451)

        response = self.client.get(reverse("orders:order_payment_print", args=(new_order.pk,)))
        self.assertContains(response, "Adeudo pendiente de pedidos anteriores: $100.00 (1 pedido)")

    def test_payment_print_omits_the_debt_line_when_nothing_is_pending(self):
        order = self.make_order(status=Order.Status.PREPARING, total=80)
        response = self.client.get(reverse("orders:order_payment_print", args=(order.pk,)))
        self.assertNotContains(response, "Adeudo pendiente")

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
                "Cambios pendientes", "Reporte de propinas", "Corte de bebidas calientes", "Corte de caja",
            ],
            "cashier:debt_board": [
                "Caja", "Saldos a favor", "Corte de terminales", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:credit_board": [
                "Caja", "Cuentas por cobrar", "Corte de terminales", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:terminal_board": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Cambios pendientes",
                "Reporte de propinas", "Corte de bebidas calientes", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:change_board": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Reporte de propinas", "Corte de bebidas calientes", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:tip_report": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Corte de bebidas calientes", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:coffee_report": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Reporte de propinas", "Corte de caja",
                "Registrar un pedido que no pagó",
            ],
            "cashier:register_cut": [
                "Caja", "Cuentas por cobrar", "Saldos a favor", "Corte de terminales",
                "Cambios pendientes", "Reporte de propinas", "Corte de bebidas calientes",
                "Registrar un pedido que no pagó",
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


class CashRegisterCutTests(TestCase):
    # NOTA: el desarrollador pidió un corte de caja general — apertura/cierre de
    # efectivo, egresos del día, y dos tablas de auditoría (pedidos sin pagar,
    # pedidos sin resolver) para asegurarse de que nada se quede pendiente al
    # cerrar el día. Los 4 importes se pueden corregir en cualquier momento.
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="cut_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.client.force_login(self.admin)
        self.today = timezone.localdate()
        self.customer = Customer.objects.create(name="Cliente corte", phone="5551110000")

    def make_order(self, *, operating_date, status=Order.Status.PREPARING, total=100, daily_number=None):
        return Order.objects.create(
            daily_number=daily_number or (3000 + Order.objects.count()),
            operating_date=operating_date, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=status, customer_name="Cliente corte",
            agenda_customer=self.customer, total=total, requested_date=operating_date,
            requested_time=timezone.localtime().time(), created_by=self.admin,
        )

    def test_visiting_the_page_auto_creates_todays_cut(self):
        self.assertFalse(CashRegisterCut.objects.filter(operating_date=self.today).exists())
        response = self.client.get(reverse("cashier:register_cut"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CashRegisterCut.objects.filter(operating_date=self.today).exists())

    def test_updating_the_four_amounts(self):
        response = self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "update_amounts", "opening_cash": "500", "closing_cash": "1200",
             "closing_card": "300", "closing_transfer": "150"},
        )
        self.assertEqual(response.status_code, 302)
        cut = CashRegisterCut.objects.get(operating_date=self.today)
        self.assertEqual(cut.opening_cash, Decimal("500"))
        self.assertEqual(cut.closing_cash, Decimal("1200"))
        self.assertEqual(cut.closing_card, Decimal("300"))
        self.assertEqual(cut.closing_transfer, Decimal("150"))
        self.assertEqual(cut.total_income, Decimal("1650"))
        self.assertEqual(cut.updated_by, self.admin)

    def test_amounts_can_be_edited_again_later(self):
        cut = CashRegisterCut.objects.create(operating_date=self.today, opening_cash=500)
        self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "update_amounts", "opening_cash": "600", "closing_cash": "0",
             "closing_card": "0", "closing_transfer": "0"},
        )
        cut.refresh_from_db()
        self.assertEqual(cut.opening_cash, Decimal("600"))

    def test_negative_amounts_are_rejected(self):
        self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "update_amounts", "opening_cash": "-1", "closing_cash": "0",
             "closing_card": "0", "closing_transfer": "0"},
        )
        cut = CashRegisterCut.objects.get(operating_date=self.today)
        self.assertEqual(cut.opening_cash, Decimal("0"))

    def test_adding_and_listing_an_expense(self):
        response = self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "add_expense", "amount": "80", "concept": "Pollo"},
        )
        self.assertEqual(response.status_code, 302)
        expense = CashRegisterExpense.objects.get()
        self.assertEqual(expense.amount, Decimal("80"))
        self.assertEqual(expense.concept, "Pollo")
        self.assertEqual(expense.registered_by, self.admin)
        page = self.client.get(reverse("cashier:register_cut"), {"date": self.today.isoformat()})
        self.assertContains(page, "Pollo")
        self.assertContains(page, "Total egresos")

    def test_expense_requires_a_positive_amount_and_a_concept(self):
        self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "add_expense", "amount": "0", "concept": "Pollo"},
        )
        self.assertFalse(CashRegisterExpense.objects.exists())

    def test_deleting_an_expense(self):
        cut = CashRegisterCut.objects.create(operating_date=self.today)
        expense = CashRegisterExpense.objects.create(cut=cut, amount=50, concept="Pan", registered_by=self.admin)
        self.client.post(
            f"{reverse('cashier:register_cut')}?date={self.today.isoformat()}",
            {"action": "delete_expense", "expense_id": expense.pk},
        )
        self.assertFalse(CashRegisterExpense.objects.filter(pk=expense.pk).exists())

    def test_shows_unpaid_orders_for_the_selected_day(self):
        order = self.make_order(operating_date=self.today, status=Order.Status.DELIVERED, total=150)
        create_customer_debt(order=order, actor=self.admin)
        response = self.client.get(reverse("cashier:register_cut"), {"date": self.today.isoformat()})
        self.assertContains(response, "$150.00")
        self.assertContains(response, order.formatted_number)

    def test_audit_tables_show_ascending_numbers_and_initial_counters(self):
        debt_order = self.make_order(
            operating_date=self.today, status=Order.Status.DELIVERED,
            total=150, daily_number=3010,
        )
        create_customer_debt(order=debt_order, actor=self.admin)
        pending_order = self.make_order(
            operating_date=self.today, status=Order.Status.PREPARING,
            daily_number=3011,
        )

        response = self.client.get(reverse("cashier:register_cut"), {"date": self.today.isoformat()})

        self.assertContains(response, 'data-unpaid-count aria-live="polite">1</span>')
        self.assertContains(response, 'data-pending-count aria-live="polite">1</span>')
        self.assertContains(response, "<th>#</th>", count=2, html=True)
        self.assertContains(response, "<tr><td>1</td><td><strong>", html=False)
        self.assertContains(response, "<tr><td>1</td><td><a", html=False)
        self.assertContains(response, debt_order.formatted_number)
        self.assertContains(response, pending_order.formatted_number)

    def test_audit_count_endpoint_reflects_changes_without_reloading_the_cut(self):
        debt_order = self.make_order(
            operating_date=self.today, status=Order.Status.DELIVERED,
            total=150, daily_number=3020,
        )
        debt = create_customer_debt(order=debt_order, actor=self.admin)
        pending_order = self.make_order(
            operating_date=self.today, status=Order.Status.PREPARING,
            daily_number=3021,
        )
        url = reverse("cashier:register_cut_audit_counts")

        response = self.client.get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.json(), {"unpaid_count": 1, "pending_count": 1})

        debt.status = CustomerDebt.Status.PAID
        debt.paid_amount = debt.original_amount
        debt.save(update_fields=("status", "paid_amount", "updated_at"))
        pending_order.status = Order.Status.DELIVERED
        pending_order.save(update_fields=("status", "updated_at"))

        response = self.client.get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.json(), {"unpaid_count": 0, "pending_count": 0})

    def test_unresolved_orders_exclude_cancelled_and_already_marked_unpaid(self):
        # NOTA: reproduce la regla exacta que pidió el desarrollador — cancelado
        # y "no pagó" cuentan como resueltos aunque su status operativo nunca
        # haya llegado a Entregado/Recogido; sólo debe sobrar el que de verdad
        # se quedó sin resolver.
        stuck_order = self.make_order(operating_date=self.today, status=Order.Status.PREPARING, daily_number=3001)
        canceled_order = self.make_order(operating_date=self.today, status=Order.Status.CANCELED, daily_number=3002)
        unpaid_order = self.make_order(operating_date=self.today, status=Order.Status.PREPARING, daily_number=3003)
        create_customer_debt(order=unpaid_order, actor=self.admin)
        delivered_order = self.make_order(operating_date=self.today, status=Order.Status.DELIVERED, daily_number=3004)

        response = self.client.get(reverse("cashier:register_cut"), {"date": self.today.isoformat()})
        # unpaid_order también debe seguir apareciendo en la tabla de pendientes
        # de PAGO (tiene un adeudo real) — sólo debe faltar en la de "sin resolver".
        pending_ids = {order.id for order in response.context["pending_orders"]}
        self.assertEqual(pending_ids, {stuck_order.id})

    def test_unresolved_orders_exclude_transfer_when_destination_table_is_closed(self):
        closed_table = DiningTable.objects.create(name="Mesa transferencia cerrada")
        closed_account = TableAccount.objects.create(
            table=closed_table,
            assigned_waiter=self.admin,
            opened_by=self.admin,
            status=TableAccount.Status.CLOSED,
            closed_at=timezone.now(),
            closed_by=self.admin,
        )
        resolved_order = self.make_order(
            operating_date=self.today,
            status=Order.Status.TRANSFERRED,
            daily_number=3030,
        )
        resolved_order.transferred_to_table = closed_account
        resolved_order.save(update_fields=("transferred_to_table", "updated_at"))

        open_table = DiningTable.objects.create(name="Mesa transferencia abierta")
        open_account = TableAccount.objects.create(
            table=open_table,
            assigned_waiter=self.admin,
            opened_by=self.admin,
            status=TableAccount.Status.OPEN,
        )
        still_pending_order = self.make_order(
            operating_date=self.today,
            status=Order.Status.TRANSFERRED,
            daily_number=3031,
        )
        still_pending_order.transferred_to_table = open_account
        still_pending_order.save(update_fields=("transferred_to_table", "updated_at"))

        response = self.client.get(
            reverse("cashier:register_cut"), {"date": self.today.isoformat()},
        )

        pending_ids = {order.id for order in response.context["pending_orders"]}
        self.assertNotIn(resolved_order.id, pending_ids)
        self.assertIn(still_pending_order.id, pending_ids)
        counts = self.client.get(
            reverse("cashier:register_cut_audit_counts"),
            {"date": self.today.isoformat()},
        ).json()
        self.assertEqual(counts["pending_count"], 1)

    def test_daily_and_weekly_history(self):
        monday = self.today - timedelta(days=self.today.weekday())
        day_one = monday
        day_two = monday + timedelta(days=1)
        CashRegisterCut.objects.create(operating_date=day_one, closing_cash=100, closing_card=50, closing_transfer=25)
        cut_two = CashRegisterCut.objects.create(operating_date=day_two, closing_cash=200, closing_card=0, closing_transfer=0)
        CashRegisterExpense.objects.create(cut=cut_two, amount=30, concept="Luz", registered_by=self.admin)

        response = self.client.get(reverse("cashier:register_cut"), {
            "date": self.today.isoformat(), "hist_from": monday.isoformat(), "hist_to": (monday + timedelta(days=6)).isoformat(),
        })
        self.assertContains(response, "$175.00")  # día 1: 100+50+25
        self.assertContains(response, "$200.00")  # día 2 ingresos
        self.assertContains(response, "$30.00")  # día 2 egresos
        # semanal: ingresos totales = 175 + 200 = 375
        self.assertContains(response, "$375.00")


class OrderTableTransferTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="transfer_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.waiter = get_user_model().objects.create_user(username="transfer_waiter")
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.other_waiter = get_user_model().objects.create_user(username="transfer_waiter_two")
        self.other_waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.order_taker = get_user_model().objects.create_user(username="transfer_order_taker")
        self.order_taker.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])

        category = Category.objects.create(name="Transferencias de prueba")
        self.product = Product.objects.create(
            category=category, name="Torta transferible", price=45, is_sold_individually=True,
        )
        self.product_two = Product.objects.create(
            category=category, name="Agua transferible", price=15, is_sold_individually=True,
        )
        self.table = DiningTable.objects.create(name="Mesa transferencias", display_order=200)
        self.table_two = DiningTable.objects.create(name="Mesa transferencias 2", display_order=201)

    def make_pickup_order(self, *, status=Order.Status.PREPARING, daily_number=None,
                          order_type=Order.OrderType.PICKUP):
        return Order.objects.create(
            daily_number=daily_number or (900 + Order.objects.count()),
            operating_date=timezone.localdate(), order_type=order_type,
            source=Order.Source.INTERNAL, status=status, customer_name="Cliente transferible",
            phone="", total=0, created_by=self.admin,
        )

    # -- transfer_order_to_table ------------------------------------------------

    def test_admin_must_pick_a_waiter_to_transfer_order_to_table(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        with self.assertRaisesMessage(ValidationError, "Selecciona a qué mesero"):
            transfer_order_to_table(order=order, table=self.table, actor=self.admin)

    def test_admin_can_assign_a_specific_waiter(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        new_account = transfer_order_to_table(
            order=order, table=self.table, actor=self.admin, assigned_waiter=self.other_waiter,
        )
        self.assertEqual(new_account.assigned_waiter_id, self.other_waiter.pk)

    def test_waiter_is_assigned_to_themselves_automatically(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        new_account = transfer_order_to_table(order=order, table=self.table, actor=self.waiter)
        self.assertEqual(new_account.assigned_waiter_id, self.waiter.pk)

    def test_transfer_order_to_table_copies_items_and_marks_order_transferred(self):
        order = self.make_pickup_order()
        item = add_internal_order_product(order=order, product=self.product, actor=self.admin)

        new_account = transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.TRANSFERRED)
        self.assertEqual(order.transferred_to_table_id, new_account.pk)
        self.assertEqual(new_account.table_id, self.table.pk)
        self.assertEqual(new_account.status, TableAccount.Status.OPEN)
        self.assertEqual(new_account.customer_name, order.customer_name)
        new_item = new_account.items.get()
        self.assertEqual(new_item.product_id, item.product_id)
        self.assertEqual(new_item.quantity, item.quantity)
        self.assertEqual(new_item.subtotal, item.subtotal)
        self.assertTrue(
            order.status_history.filter(to_status=Order.Status.TRANSFERRED).exists()
        )

    def test_transfer_accepts_delivery_orders(self):
        order = self.make_pickup_order(order_type=Order.OrderType.DELIVERY)
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        new_account = transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.TRANSFERRED)
        self.assertEqual(order.transferred_to_table_id, new_account.pk)
        self.assertEqual(new_account.items.count(), 1)

    def test_transfer_rejects_inactive_statuses(self):
        for status in (
            Order.Status.CANCELED, Order.Status.DELIVERED,
            Order.Status.PICKED_UP, Order.Status.TRANSFERRED,
        ):
            with self.subTest(status=status):
                order = self.make_pickup_order(status=status, daily_number=800 + Order.objects.count())
                with self.assertRaisesMessage(ValidationError, "ya no está activo"):
                    transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    def test_transfer_rejects_order_without_items(self):
        order = self.make_pickup_order()
        with self.assertRaisesMessage(ValidationError, "Agrega al menos un producto"):
            transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    def test_transfer_rejects_incomplete_package_items(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        OrderItem.objects.create(
            order=order, item_type=OrderItem.ItemType.PRODUCT, product=self.product,
            product_name_snapshot=self.product.name, unit_price=self.product.price,
            quantity=1, subtotal=self.product.price, is_package_candidate=True,
            tortillas=False, beans=False,
        )
        with self.assertRaisesMessage(ValidationError, "comida incompleta"):
            transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    def test_transfer_rejects_orders_with_credit_applied(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        order.credit_applied = Decimal("20")
        order.save(update_fields=("credit_applied",))
        with self.assertRaisesMessage(ValidationError, "saldo a favor aplicado"):
            transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    def test_transfer_rejects_inactive_table(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.table.is_active = False
        self.table.save(update_fields=("is_active",))
        with self.assertRaisesMessage(ValidationError, "desactivada"):
            transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    def test_transfer_rejects_table_with_open_account(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        open_table_account(table=self.table, assigned_waiter=self.other_waiter, opened_by=self.other_waiter)
        with self.assertRaisesMessage(ValidationError, "ya tiene una cuenta abierta"):
            transfer_order_to_table(order=order, table=self.table, actor=self.waiter)

    # -- transfer_table_to_order -------------------------------------------------

    def test_transfer_table_to_order_creates_new_order_for_a_walk_in_table(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        add_product_to_table(account=account, product=self.product, added_by=self.waiter)

        new_order = transfer_table_to_order(table_account=account, actor=self.waiter)

        account.refresh_from_db()
        self.assertEqual(account.status, TableAccount.Status.TRANSFERRED)
        self.assertEqual(new_order.order_type, Order.OrderType.PICKUP)
        self.assertEqual(new_order.status, Order.Status.PREPARING)
        self.assertEqual(new_order.transferred_from_table_id, account.pk)
        self.assertEqual(new_order.items.count(), 1)
        self.assertEqual(new_order.total, self.product.price)

    def test_transfer_table_to_order_reopens_the_originating_order(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        new_account = transfer_order_to_table(order=order, table=self.table, actor=self.waiter)
        # El mesero agrega otro producto ya en la mesa antes de regresarlo a Recoger.
        add_product_to_table(account=new_account, product=self.product_two, added_by=self.waiter)

        reopened_order = transfer_table_to_order(table_account=new_account, actor=self.waiter)

        self.assertEqual(reopened_order.pk, order.pk)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PREPARING)
        self.assertIsNone(order.transferred_to_table_id)
        # Las partidas viejas se reemplazan por el estado actual de la mesa (2 partidas).
        self.assertEqual(order.items.count(), 2)
        new_account.refresh_from_db()
        self.assertEqual(new_account.status, TableAccount.Status.TRANSFERRED)

    def test_transfer_table_to_order_rejects_non_open_accounts(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        add_product_to_table(account=account, product=self.product, added_by=self.waiter)
        account.status = TableAccount.Status.CLOSED
        account.save(update_fields=("status",))
        with self.assertRaisesMessage(ValidationError, "ya no está abierta"):
            transfer_table_to_order(table_account=account, actor=self.waiter)

    def test_transfer_table_to_order_rejects_empty_accounts(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        with self.assertRaisesMessage(ValidationError, "Agrega al menos un producto"):
            transfer_table_to_order(table_account=account, actor=self.waiter)

    def test_transfer_table_to_order_rejects_incomplete_package_items(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        add_product_to_table(account=account, product=self.product, added_by=self.waiter)
        TableAccountItem.objects.create(
            account=account, product=self.product, product_name_snapshot=self.product.name,
            unit_price=self.product.price, quantity=1, subtotal=self.product.price,
            is_package_candidate=True, added_by=self.waiter,
        )
        with self.assertRaisesMessage(ValidationError, "comida incompleta"):
            transfer_table_to_order(table_account=account, actor=self.waiter)

    # -- stock moves between channels --------------------------------------------

    def test_transfer_moves_reserved_stock_between_order_and_table_channels(self):
        today = timezone.localdate()
        orders_stock = DailyProductStock.objects.create(
            date=today, product=self.product, channel=DailyProductStock.Channel.ORDERS, initial_quantity=3,
        )
        table_stock = DailyProductStock.objects.create(
            date=today, product=self.product, channel=DailyProductStock.Channel.TABLE, initial_quantity=3,
        )
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.assertEqual(orders_stock.available_quantity, 2)
        self.assertEqual(table_stock.available_quantity, 3)

        new_account = transfer_order_to_table(order=order, table=self.table, actor=self.waiter)
        self.assertEqual(orders_stock.available_quantity, 3)
        self.assertEqual(table_stock.available_quantity, 2)

        transfer_table_to_order(table_account=new_account, actor=self.waiter)
        self.assertEqual(orders_stock.available_quantity, 2)
        self.assertEqual(table_stock.available_quantity, 3)

    # -- view-level permissions and redirects -------------------------------------

    def test_transfer_form_is_marked_to_skip_the_ajax_status_handler(self):
        # NOTA: bug real reportado — el formulario "Pasar a mesa" del tablero de
        # Pedidos caía dentro del manejador genérico de AJAX de order-list.js (que
        # espera JSON), y como order_transfer_to_table siempre responde con una
        # redirección normal (a la mesa nueva si funcionó, o de vuelta a Pedidos con
        # un mensaje de error si no), el navegador mostraba "No se pudo cambiar el
        # estado" incluso cuando la transferencia sí se había hecho en el servidor.
        # Verifica que la plantilla ya trae el atributo que lo excluye de ese
        # manejador (mismo arreglo ya aplicado antes a "No pagó").
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.client.force_login(self.waiter)
        response = self.client.get(reverse("orders:order_list"))
        self.assertContains(response, "data-order-transfer-form")

    def test_order_transfer_to_table_ajax_returns_confirmed_destination(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.client.force_login(self.waiter)

        response = self.client.post(
            reverse("orders:order_transfer_to_table", args=(order.pk,)),
            {"table_id": self.table.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        account = TableAccount.objects.get(pk=response.json()["account_id"])
        self.assertEqual(
            response.json()["redirect_url"],
            reverse("tables:table_detail", args=(account.pk,)),
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.TRANSFERRED)

    def test_delivery_order_also_exposes_transfer_to_table(self):
        order = self.make_pickup_order(order_type=Order.OrderType.DELIVERY)
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.client.force_login(self.waiter)

        response = self.client.get(reverse("orders:order_list"))

        rendered_order = next(item for item in response.context["delivery_orders"] if item.pk == order.pk)
        self.assertTrue(rendered_order.can_transfer_to_table)
        self.assertContains(
            response, reverse("orders:order_transfer_to_table", args=(order.pk,)),
        )

    def test_order_transfer_to_table_view_rejects_roles_without_access(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.client.force_login(self.order_taker)
        response = self.client.post(
            reverse("orders:order_transfer_to_table", args=(order.pk,)),
            {"table_id": self.table.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_order_transfer_to_table_view_success_redirects_to_table_detail(self):
        order = self.make_pickup_order()
        add_internal_order_product(order=order, product=self.product, actor=self.admin)
        self.client.force_login(self.waiter)
        response = self.client.post(
            reverse("orders:order_transfer_to_table", args=(order.pk,)),
            {"table_id": self.table.pk},
        )
        order.refresh_from_db()
        new_account = order.transferred_to_table
        self.assertRedirects(response, reverse("tables:table_detail", args=(new_account.pk,)))

    def test_table_transfer_to_order_view_rejects_roles_without_access(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        add_product_to_table(account=account, product=self.product, added_by=self.waiter)
        self.client.force_login(self.order_taker)
        response = self.client.post(reverse("tables:table_transfer_to_order", args=(account.pk,)))
        self.assertEqual(response.status_code, 403)

    def test_table_transfer_to_order_view_success_redirects_to_order_list(self):
        account = open_table_account(table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter)
        add_product_to_table(account=account, product=self.product, added_by=self.waiter)
        self.client.force_login(self.waiter)
        response = self.client.post(reverse("tables:table_transfer_to_order", args=(account.pk,)))
        self.assertRedirects(response, reverse("orders:order_list"))


class AutoMealOutOfOrderTests(TestCase):
    # NOTA TEMPORAL PARA APRENDIZAJE: cubre el arreglo del "stopper" reportado por el
    # desarrollador — antes, capturar el mismo tiempo (primero/segundo/tercero) dos
    # veces seguidas bloqueaba con "Completa la comida actual antes de iniciar otra",
    # obligando a armar las comidas corridas/ejecutivas una por una y en orden estricto.
    # Borra esta nota después de leerla.
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="auto_meal_order_actor")
        self.actor.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        category = Category.objects.create(name="Comida corrida prueba orden")
        self.first_product = Product.objects.create(
            category=category, name="Primer tiempo prueba", price=0,
            component_type=Product.ComponentType.VARIABLE_FIRST_COURSE, is_sold_individually=False,
        )
        self.second_product = Product.objects.create(
            category=category, name="Segundo tiempo prueba", price=0,
            component_type=Product.ComponentType.SECOND_COURSE, is_sold_individually=False,
        )
        self.main_product = Product.objects.create(
            category=category, name="Guisado prueba", price=45,
            component_type=Product.ComponentType.BEEF_STEW, is_sold_individually=False,
        )
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(
            date=today, status=DailyMenu.Status.PUBLISHED,
            variable_first_course=self.first_product, second_course_one=self.second_product,
        )
        self.menu.set_stews([self.main_product])
        for product in (self.first_product, self.second_product, self.main_product):
            DailyProductStock.objects.create(
                date=today, daily_menu=self.menu, product=product,
                channel=DailyProductStock.Channel.ORDERS, initial_quantity=10,
            )
        MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={
                "name": "Comida corrida prueba orden", "price_without_water": 70,
                "price_with_water": 80, "table_refill_price": 10,
            },
        )
        self.order = Order.objects.create(
            daily_number=995, operating_date=today, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=0, created_by=self.actor,
        )
        self.client.force_login(self.actor)

    def add(self, product):
        response = self.client.post(
            reverse("orders:internal_order_auto_meal_add", args=(self.order.pk, product.pk)),
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_several_meals_can_be_started_out_of_order(self):
        for _ in range(3):
            data = self.add(self.first_product)
            self.assertTrue(data["ok"])
            self.assertFalse(data["auto_package_created"])
        for _ in range(3):
            data = self.add(self.second_product)
            self.assertTrue(data["ok"])
            self.assertFalse(data["auto_package_created"])
        completed = [self.add(self.main_product)["auto_package_created"] for _ in range(3)]
        self.assertEqual(completed, [True, True, True])
        self.order.refresh_from_db()
        self.assertEqual(self.order.items.filter(item_type=OrderItem.ItemType.PACKAGE).count(), 3)
        self.assertFalse(self.order.items.filter(is_package_candidate=True).exists())

    def test_a_single_meal_still_completes_in_order(self):
        self.add(self.first_product)
        self.add(self.second_product)
        data = self.add(self.main_product)
        self.assertTrue(data["auto_package_created"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.items.filter(item_type=OrderItem.ItemType.PACKAGE).count(), 1)
