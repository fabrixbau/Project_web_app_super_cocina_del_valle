from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import WAITER
from menu.models import Category, DailyMenu, DailyProductStock, Product, StockMovement

from .models import DiningTable, TableAccount, TableActivity
from .services import add_daily_menu_product_to_table, change_item_in_ticket, close_table_account


class TableCustomerAutosaveTests(TestCase):
    def setUp(self):
        self.waiter = get_user_model().objects.create_user(
            username="mesero_autoguardado",
            password="test-password",
        )
        self.waiter.groups.add(Group.objects.get(name=WAITER))
        self.table = DiningTable.objects.create(name="Mesa prueba", display_order=100)
        self.account = TableAccount.objects.create(
            table=self.table,
            assigned_waiter=self.waiter,
            opened_by=self.waiter,
        )
        self.client.force_login(self.waiter)

    def test_customer_name_is_saved_through_ajax(self):
        response = self.client.post(
            reverse("tables:table_customer_name_update", args=(self.account.pk,)),
            {"customer_name": "  Ana   López  "},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "customer_name": "Ana López"})
        self.account.refresh_from_db()
        self.assertEqual(self.account.customer_name, "Ana López")
        self.assertEqual(
            self.account.activities.filter(action=TableActivity.Action.CUSTOMER).count(),
            1,
        )

    def test_same_name_does_not_duplicate_activity(self):
        self.account.customer_name = "Ana"
        self.account.save(update_fields=("customer_name",))
        url = reverse("tables:table_customer_name_update", args=(self.account.pk,))

        self.client.post(
            url,
            {"customer_name": "Ana"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertFalse(
            self.account.activities.filter(action=TableActivity.Action.CUSTOMER).exists(),
        )


class TableInventoryIntegrationTests(TestCase):
    def setUp(self):
        self.waiter = get_user_model().objects.create_user(username="stock_waiter")
        category = Category.objects.create(name="Comida corrida")
        self.product = Product.objects.create(
            category=category, name="Arroz de prueba", price=25,
            component_type=Product.ComponentType.SECOND_COURSE,
            is_sold_individually=False,
        )
        self.menu = DailyMenu.objects.create(
            date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
            second_course_one=self.product,
        )
        self.stock = DailyProductStock.objects.create(
            date=self.menu.date, daily_menu=self.menu, product=self.product,
            channel=DailyProductStock.Channel.TABLE, initial_quantity=2,
        )
        table = DiningTable.objects.create(name="Mesa inventario", display_order=101)
        self.account = TableAccount.objects.create(
            table=table, assigned_waiter=self.waiter, opened_by=self.waiter,
        )

    def test_add_increase_decrease_and_remove_keep_stock_in_sync(self):
        item = add_daily_menu_product_to_table(
            account=self.account, product=self.product, daily_menu=self.menu,
            added_by=self.waiter,
        )
        self.assertEqual(self.stock.available_quantity, 1)

        change_item_in_ticket(
            account=self.account, item=item, action="increase", changed_by=self.waiter,
        )
        self.assertEqual(self.stock.available_quantity, 0)
        with self.assertRaisesMessage(ValidationError, "Disponibles: 0"):
            change_item_in_ticket(
                account=self.account, item=item, action="increase", changed_by=self.waiter,
            )

        change_item_in_ticket(
            account=self.account, item=item, action="decrease", changed_by=self.waiter,
        )
        self.assertEqual(self.stock.available_quantity, 1)
        change_item_in_ticket(
            account=self.account, item=item, action="remove", changed_by=self.waiter,
        )
        self.assertEqual(self.stock.available_quantity, 2)

    def test_closing_changes_reservation_to_consumption(self):
        add_daily_menu_product_to_table(
            account=self.account, product=self.product, daily_menu=self.menu,
            added_by=self.waiter,
        )
        close_table_account(
            account=self.account,
            cleaned_data={"tip_amount": 0, "payment_method": "cash", "cash_tendered": 25},
            closed_by=self.waiter,
        )

        movement = self.stock.movements.get()
        self.assertEqual(movement.reason, StockMovement.Reason.CONSUMPTION)
        self.assertEqual(self.stock.available_quantity, 1)
