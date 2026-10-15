from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from accounts.roles import WAITER
from config.printing import table_print_context

from .models import DiningTable, TableAccount, TableAccountItem


class TableCashCloseTests(TestCase):
    """Mesas en efectivo: sin propina ni efectivo recibido; el ticket de cobro no lleva
    método de pago, "Paga con" ni CAMBIO. Terminal/Transferencia sin cambios (2026-10-15)."""

    def setUp(self):
        self.waiter = get_user_model().objects.create_user(username="mesero_efectivo")
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.client.force_login(self.waiter)
        table = DiningTable.objects.create(name="Mesa efectivo", display_order=401)
        self.account = TableAccount.objects.create(table=table, assigned_waiter=self.waiter, opened_by=self.waiter)
        TableAccountItem.objects.create(
            account=self.account, product_name_snapshot="Enchiladas", unit_price=80, subtotal=80, added_by=self.waiter,
        )

    def close(self, **data):
        return self.client.post(reverse("tables:table_close", args=(self.account.pk,)), {
            "responsible_waiter": self.waiter.pk, **data,
        })

    def test_cash_closes_without_amount_received_or_tip(self):
        self.close(payment_method="cash", tip_amount="20")
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, TableAccount.Status.CLOSED)
        self.assertEqual(self.account.total_paid, Decimal("80"))
        self.assertEqual(self.account.tip_amount, 0)
        self.assertIsNone(self.account.cash_tendered)
        self.assertIsNone(self.account.change_given)
        ticket = render_to_string("printing/payment_ticket.html", {**table_print_context(self.account), "items": []})
        self.assertNotIn("Método de pago", ticket)
        self.assertNotIn("Paga con", ticket)
        self.assertNotIn("CAMBIO", ticket)
        self.assertIn("80.00", ticket)

    def test_card_keeps_tip_and_payment_method_on_ticket(self):
        self.close(payment_method="card", tip_amount="10")
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, TableAccount.Status.CLOSED)
        self.assertEqual(self.account.total_paid, Decimal("90"))
        ticket = render_to_string("printing/payment_ticket.html", {**table_print_context(self.account), "items": []})
        self.assertIn("Método de pago", ticket)
        self.assertIn("Terminal", ticket)
