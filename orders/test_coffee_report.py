from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from menu.models import Category, Product
from tables.models import DiningTable, TableAccount, TableAccountItem

from .coffee_report import coffee_sales_for_date
from .models import CoffeeSettlement, Order, OrderItem


class CoffeeReportTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username="coffee_admin", email="coffee@example.test", password="test-password",
        )
        self.client.force_login(self.actor)
        category = Category.objects.create(name="Bebidas calientes")
        self.product = Product.objects.create(category=category, name="Capuchino", price=40)
        self.date = timezone.localdate()
        self.order = Order.objects.create(
            daily_number=993, operating_date=self.date, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.PICKED_UP,
            customer_name="Mostrador", phone="", total=100, created_by=self.actor,
        )
        self.snapshot = {"groups": [{"group": "Ingredientes", "selected": [
            {"name": "Grande", "price_adjustment": "5.00"},
            {"name": "Deslactosada", "price_adjustment": "5.00"},
        ]}]}
        OrderItem.objects.create(
            order=self.order, item_type=OrderItem.ItemType.PRODUCT, product=self.product,
            product_name_snapshot="Capuchino", configuration_snapshot=self.snapshot,
            unit_price=50, quantity=2, subtotal=100, tortillas=False, beans=False,
        )

    def test_finalized_sales_are_separate_from_open_accounts(self):
        table = DiningTable.objects.create(name="Mesa café")
        account = TableAccount.objects.create(table=table, assigned_waiter=self.actor, opened_by=self.actor)
        TableAccountItem.objects.create(
            account=account, product=self.product, item_type=TableAccountItem.ItemType.PRODUCT,
            product_name_snapshot="Capuchino", configuration_snapshot={"groups": [{"selected": [{"name": "Entera"}]}]},
            unit_price=40, quantity=1, subtotal=40, added_by=self.actor,
        )
        report = coffee_sales_for_date(self.date)
        self.assertEqual(report["sales_total"], Decimal("100.00"))
        self.assertEqual(report["pending_total"], Decimal("40.00"))
        self.assertEqual(report["summary"][0]["size"], "Grande")
        self.assertEqual(report["summary"][0]["milk"], "Deslactosada")
        account.status = TableAccount.Status.CLOSED
        account.save(update_fields=("status",))
        self.assertEqual(coffee_sales_for_date(self.date)["sales_total"], Decimal("140.00"))

    def test_settlement_and_csv(self):
        url = reverse("cashier:coffee_settlement")
        response = self.client.post(url, {"date": self.date.isoformat(), "amount": "80.00"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CoffeeSettlement.objects.count(), 1)
        self.client.post(url, {"date": self.date.isoformat(), "amount": "30.00"})
        self.assertEqual(CoffeeSettlement.objects.count(), 1)
        page = self.client.get(reverse("cashier:coffee_report"), {"date": self.date.isoformat()})
        self.assertContains(page, "20.00")
        csv_response = self.client.get(reverse("cashier:coffee_report"), {"date": self.date.isoformat(), "download": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Capuchino", csv_response.content.decode("utf-8"))
