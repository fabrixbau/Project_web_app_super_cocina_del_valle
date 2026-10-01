from decimal import Decimal
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, ORDER_TAKER, WAITER
from menu.models import Category, Product
from tables.models import DiningTable, TableAccount, TableAccountItem

from .models import Customer, CustomerCreditMovement, CustomerDebt, CustomerDebtMovement, Order
from .services import add_customer_credit, apply_credit_to_debts, create_customer_debt, suggested_credit_allocation
from .views import _terminal_expected


class CreditVersusDebtTests(TestCase):
    """Pagar pedidos adeudados con el saldo a favor del cliente (escenarios 1–4)."""

    def setUp(self):
        self.admin = self.user("credito_admin", ADMIN)
        self.customer = Customer.objects.create(name="Cliente abonos", phone="5550001111")
        self.client.force_login(self.admin)

    def user(self, username, role):
        user = get_user_model().objects.create_user(username=username)
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

    def debt(self, amount):
        order = Order.objects.create(
            daily_number=3000 + Order.objects.count(), operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL, status=Order.Status.PICKED_UP,
            customer_name=self.customer.name, agenda_customer=self.customer, total=amount,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
            created_by=self.admin,
        )
        return create_customer_debt(order=order, actor=self.admin)

    def deposit(self, amount):
        add_customer_credit(customer=self.customer, amount=amount, payment_method=Order.PaymentMethod.CASH, actor=self.admin)

    def balance(self):
        self.customer.refresh_from_db()
        return self.customer.credit_balance

    def test_scenario_1_deposit_pays_two_debts_and_leaves_850(self):
        first, second = self.debt(100), self.debt(50)
        self.deposit(1000)
        apply_credit_to_debts(customer=self.customer, allocations={first.pk: "100", second.pk: "50"}, actor=self.admin)

        self.assertEqual(self.balance(), Decimal("850"))
        for debt in (first, second):
            debt.refresh_from_db()
            self.assertEqual(debt.status, CustomerDebt.Status.PAID)
            movement = debt.movements.get(action=CustomerDebtMovement.Action.CREDIT)
            self.assertEqual(movement.credit_movement.action, CustomerCreditMovement.Action.REDEMPTION)
            self.assertEqual(movement.credit_movement.order, debt.order)
            self.assertEqual(movement.payment_method, "")

    def test_scenario_2_new_debt_covered_by_credit_leaves_900(self):
        self.deposit(1000)
        debt = self.debt(100)
        apply_credit_to_debts(customer=self.customer, allocations={debt.pk: "100"}, actor=self.admin)

        debt.refresh_from_db()
        self.assertEqual(debt.status, CustomerDebt.Status.PAID)
        self.assertEqual(self.balance(), Decimal("900"))

    def test_scenario_3_partial_credit_leaves_50_owed_and_zero_credit(self):
        self.deposit(100)
        debt = self.debt(150)
        apply_credit_to_debts(customer=self.customer, allocations={debt.pk: "100"}, actor=self.admin)

        debt.refresh_from_db()
        self.assertEqual(debt.status, CustomerDebt.Status.PARTIAL)
        self.assertEqual(debt.paid_amount, Decimal("100"))
        self.assertEqual(debt.balance, Decimal("50"))
        self.assertEqual(self.balance(), Decimal("0"))

    def test_scenario_4_settles_one_and_partially_pays_the_other(self):
        first, second = self.debt(400), self.debt(200)
        self.deposit(500)
        apply_credit_to_debts(customer=self.customer, allocations={first.pk: "400", second.pk: "100"}, actor=self.admin)

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, CustomerDebt.Status.PAID)
        self.assertEqual(second.status, CustomerDebt.Status.PARTIAL)
        self.assertEqual(second.balance, Decimal("100"))
        self.assertEqual(self.balance(), Decimal("0"))

    def test_suggestion_pays_oldest_first_and_puts_the_new_debt_first(self):
        first, second = self.debt(400), self.debt(200)
        self.assertEqual(
            suggested_credit_allocation(credit=Decimal("500"), debts=[first, second]),
            {first.pk: Decimal("400"), second.pk: Decimal("100")},
        )
        self.assertEqual(
            suggested_credit_allocation(credit=Decimal("500"), debts=[first, second], focus_debt_id=second.pk),
            {second.pk: Decimal("200"), first.pk: Decimal("300")},
        )

    def test_rejects_more_than_the_credit_or_the_debt_without_changing_anything(self):
        debt = self.debt(100)
        self.deposit(80)
        with self.assertRaisesMessage(ValidationError, "saldo a favor disponible"):
            apply_credit_to_debts(customer=self.customer, allocations={debt.pk: "90"}, actor=self.admin)
        self.deposit(100)
        with self.assertRaisesMessage(ValidationError, "sólo le faltan"):
            apply_credit_to_debts(customer=self.customer, allocations={debt.pk: "150"}, actor=self.admin)
        debt.refresh_from_db()
        self.assertEqual(debt.paid_amount, Decimal("0"))
        self.assertEqual(self.balance(), Decimal("180"))

    def test_payments_with_credit_do_not_count_again_in_the_cash_cut(self):
        debt = self.debt(100)
        self.deposit(100)
        before = _terminal_expected(timezone.localdate(), payment_method=Order.PaymentMethod.CASH)["total"]
        apply_credit_to_debts(customer=self.customer, allocations={debt.pk: "100"}, actor=self.admin)
        after = _terminal_expected(timezone.localdate(), payment_method=Order.PaymentMethod.CASH)["total"]
        self.assertEqual(before, after)

    # ---- Preguntas automáticas -------------------------------------------------------

    def test_deposit_with_open_debts_asks_to_apply_the_credit(self):
        self.debt(100)
        response = self.client.post(reverse("cashier:credit_deposit"), {
            "customer_id": self.customer.pk, "amount": "1000", "payment_method": Order.PaymentMethod.CASH,
        })
        self.assertTrue(response["Location"].startswith(reverse("cashier:credit_apply", args=(self.customer.pk,))))

    def test_deposit_without_debts_does_not_ask(self):
        response = self.client.post(reverse("cashier:credit_deposit"), {
            "customer_id": self.customer.pk, "amount": "1000", "payment_method": Order.PaymentMethod.CASH,
        })
        self.assertNotIn("aplicar", response["Location"])

    def test_unpaid_order_with_credit_asks_to_cover_it(self):
        self.deposit(1000)
        order = Order.objects.create(
            daily_number=3999, operating_date=timezone.localdate(), order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.PICKED_UP, customer_name=self.customer.name,
            agenda_customer=self.customer, total=100, created_by=self.admin,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
        )
        response = self.client.post(reverse("cashier:order_debt_create", args=(order.pk,)), {"next": "/app/pedidos/"})
        location = urlparse(response["Location"])
        self.assertEqual(location.path, reverse("cashier:credit_apply", args=(self.customer.pk,)))
        self.assertEqual(parse_qs(location.query)["debt"], [str(order.customer_debt.pk)])

    def test_apply_screen_posts_the_selected_amounts(self):
        first, second = self.debt(400), self.debt(200)
        self.deposit(500)
        url = reverse("cashier:credit_apply", args=(self.customer.pk,))
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {
            "next": "/app/caja/adeudos/", f"apply_{first.pk}": "1", f"amount_{first.pk}": "400",
            f"apply_{second.pk}": "1", f"amount_{second.pk}": "100",
        })
        self.assertEqual(response["Location"], "/app/caja/adeudos/")
        second.refresh_from_db()
        self.assertEqual(second.balance, Decimal("100"))
        self.assertEqual(self.balance(), Decimal("0"))

    def test_order_taker_can_apply_credit(self):
        debt = self.debt(100)
        self.deposit(100)
        self.client.force_login(self.user("credito_telefonista", ORDER_TAKER))
        response = self.client.post(reverse("cashier:credit_apply", args=(self.customer.pk,)), {
            f"apply_{debt.pk}": "1", f"amount_{debt.pk}": "100",
        })
        self.assertEqual(response.status_code, 302)
        debt.refresh_from_db()
        self.assertEqual(debt.status, CustomerDebt.Status.PAID)

    def test_waiter_only_sees_the_table_debt_just_registered(self):
        older = self.debt(100)
        self.deposit(500)
        waiter = self.user("credito_mesero", WAITER)
        table = DiningTable.objects.create(name="Mesa saldo", display_order=150)
        account = TableAccount.objects.create(table=table, assigned_waiter=waiter, opened_by=waiter)
        product = Product.objects.create(category=Category.objects.create(name="Antojitos saldo"), name="Taco", price=100)
        TableAccountItem.objects.create(
            account=account, product=product, product_name_snapshot=product.name,
            unit_price=100, quantity=1, subtotal=100, added_by=waiter,
        )
        self.client.force_login(waiter)
        response = self.client.post(
            reverse("tables:table_register_unpaid", args=(account.pk,)), {"customer_id": self.customer.pk},
        )
        location = urlparse(response["Location"])
        self.assertEqual(location.path, reverse("cashier:credit_apply", args=(self.customer.pk,)))
        new_debt_id = int(parse_qs(location.query)["debt"][0])
        page = self.client.get(response["Location"])
        self.assertContains(page, f"amount_{new_debt_id}")
        self.assertNotContains(page, f"amount_{older.pk}")
        # Sin `?debt=` el mesero no tiene nada que aplicar y regresa.
        self.assertEqual(self.client.get(reverse("cashier:credit_apply", args=(self.customer.pk,))).status_code, 302)
