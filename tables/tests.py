import json
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import WAITER
from menu.models import Category, DailyMenu, DailyProductStock, Product, StockMovement

from .models import DiningTable, TableAccount, TableAccountItem, TableActivity
from .services import (
    add_daily_menu_product_to_table, change_item_in_ticket, close_table_account,
    split_and_close_table_account,
)


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
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
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
            cleaned_data={"tip_amount": 0, "payment_method": "cash", "cash_tendered": 25, "responsible_waiter": self.waiter},
            closed_by=self.waiter,
        )

        movement = self.stock.movements.get()
        self.assertEqual(movement.reason, StockMovement.Reason.CONSUMPTION)
        self.assertEqual(self.stock.available_quantity, 1)


class TableSplitCloseTests(TestCase):
    def setUp(self):
        self.waiter = get_user_model().objects.create_user(username="split_waiter")
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.table = DiningTable.objects.create(name="Mesa divide", display_order=102)
        self.account = TableAccount.objects.create(
            table=self.table, assigned_waiter=self.waiter, opened_by=self.waiter,
        )
        self.item_a = TableAccountItem.objects.create(
            account=self.account, product_name_snapshot="Consomé", unit_price=50, subtotal=50,
            added_by=self.waiter,
        )
        self.item_b = TableAccountItem.objects.create(
            account=self.account, product_name_snapshot="Refresco", unit_price=30, subtotal=30,
            added_by=self.waiter,
        )
        self.client.force_login(self.waiter)

    def test_split_dialog_item_data_has_real_item_ids(self):
        # NOTA: el panel de dividir arma su lista de artículos en el cliente (JS) a partir
        # de este json_script, para que refleje el ticket real incluso si se agregaron o
        # quitaron artículos por AJAX después de cargar la página — no una foto congelada
        # del momento de la carga. ticket_summary() usa la clave "item_id", no "id"; esta
        # prueba evita que ese nombre de campo se rompa otra vez sin que nadie lo note.
        response = self.client.get(reverse("tables:table_detail", args=(self.account.pk,)))
        self.assertEqual(response.status_code, 200)
        match = re.search(
            r'<script id="table-ticket-items-data"[^>]*>(.*?)</script>',
            response.content.decode(), re.S,
        )
        self.assertIsNotNone(match, "No se encontró el json_script de artículos del ticket.")
        items = json.loads(match.group(1))
        item_ids = {item["item_id"] for item in items}
        self.assertEqual(item_ids, {self.item_a.pk, self.item_b.pk})

    def split_payload(self, **overrides):
        payload = {
            "responsible_waiter": self.waiter.pk,
            "splits": [
                {"items": [{"item_id": self.item_a.pk, "quantity": 1}], "payment_method": "cash", "tip_amount": "5", "cash_tendered": "60"},
                {"items": [{"item_id": self.item_b.pk, "quantity": 1}], "payment_method": "card", "tip_amount": "10"},
            ],
        }
        payload.update(overrides)
        return payload

    def test_split_service_closes_two_accounts_sharing_the_table(self):
        accounts = split_and_close_table_account(
            account=self.account,
            splits=[
                {"item_quantities": {self.item_a.pk: 1}, "payment_method": "cash", "tip_amount": Decimal("5"), "cash_tendered": Decimal("60")},
                {"item_quantities": {self.item_b.pk: 1}, "payment_method": "card", "tip_amount": Decimal("10"), "cash_tendered": None},
            ],
            responsible_waiter=self.waiter, closed_by=self.waiter,
        )
        self.assertEqual(len(accounts), 2)
        first, second = accounts
        self.assertEqual(first.pk, self.account.pk)
        self.assertNotEqual(second.pk, self.account.pk)
        self.assertEqual(second.table_id, self.account.table_id)
        for account in accounts:
            self.assertEqual(account.status, TableAccount.Status.CLOSED)
            self.assertEqual(account.assigned_waiter_id, self.waiter.pk)
            self.assertEqual(account.tip_recipient_id, self.waiter.pk)
        self.assertEqual(first.subtotal_closed, 50)
        self.assertEqual(first.total_paid, 55)
        self.assertEqual(second.subtotal_closed, 30)
        self.assertEqual(second.total_paid, 40)
        self.assertEqual(TableAccount.objects.filter(table=self.table, status=TableAccount.Status.OPEN).count(), 0)

    def test_split_service_rejects_unassigned_items(self):
        self.item_c = TableAccountItem.objects.create(
            account=self.account, product_name_snapshot="Postre", unit_price=20, subtotal=20,
            added_by=self.waiter,
        )
        with self.assertRaisesMessage(ValidationError, "deben quedar asignados"):
            split_and_close_table_account(
                account=self.account,
                splits=[
                    {"item_quantities": {self.item_a.pk: 1}, "payment_method": "cash", "tip_amount": Decimal("0"), "cash_tendered": Decimal("50")},
                    {"item_quantities": {self.item_b.pk: 1}, "payment_method": "card", "tip_amount": Decimal("0")},
                ],
                responsible_waiter=self.waiter, closed_by=self.waiter,
            )

    def test_split_service_rejects_quantity_mismatch_for_an_item(self):
        with self.assertRaisesMessage(ValidationError, "deben quedar asignados"):
            split_and_close_table_account(
                account=self.account,
                splits=[
                    {"item_quantities": {self.item_a.pk: 1, self.item_b.pk: 1}, "payment_method": "cash", "tip_amount": Decimal("0"), "cash_tendered": Decimal("80")},
                    {"item_quantities": {self.item_b.pk: 1}, "payment_method": "card", "tip_amount": Decimal("0")},
                ],
                responsible_waiter=self.waiter, closed_by=self.waiter,
            )

    def test_split_service_splits_a_grouped_item_unit_by_unit(self):
        # Dos comidas idénticas agrupadas en una sola partida (quantity=2) deben poder
        # repartirse una a cada cuenta, en vez de forzar a que viajen juntas.
        self.item_a.quantity = 2
        self.item_a.subtotal = self.item_a.unit_price * 2
        self.item_a.save(update_fields=["quantity", "subtotal"])
        accounts = split_and_close_table_account(
            account=self.account,
            splits=[
                {"item_quantities": {self.item_a.pk: 1}, "payment_method": "cash", "tip_amount": Decimal("0"), "cash_tendered": Decimal("50")},
                {"item_quantities": {self.item_a.pk: 1, self.item_b.pk: 1}, "payment_method": "card", "tip_amount": Decimal("0")},
            ],
            responsible_waiter=self.waiter, closed_by=self.waiter,
        )
        first, second = accounts
        self.assertEqual(first.subtotal_closed, 50)
        self.assertEqual(second.subtotal_closed, 80)
        self.assertEqual(
            sum(TableAccountItem.objects.filter(account__in=accounts).values_list("quantity", flat=True)), 3,
        )

    def test_split_view_closes_the_table_and_redirects_to_the_map(self):
        response = self.client.post(
            reverse("tables:table_split_close", args=(self.account.pk,)),
            data=self.split_payload(), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["redirect_url"], reverse("tables:table_map"))
        self.account.refresh_from_db()
        self.assertEqual(self.account.status, TableAccount.Status.CLOSED)
        self.assertEqual(TableAccount.objects.filter(table=self.table).count(), 2)

    def test_split_view_splits_a_grouped_item_between_two_accounts(self):
        self.item_a.quantity = 2
        self.item_a.subtotal = self.item_a.unit_price * 2
        self.item_a.save(update_fields=["quantity", "subtotal"])
        response = self.client.post(
            reverse("tables:table_split_close", args=(self.account.pk,)),
            data=self.split_payload(splits=[
                {"items": [{"item_id": self.item_a.pk, "quantity": 1}], "payment_method": "cash", "tip_amount": "0", "cash_tendered": "50"},
                {"items": [{"item_id": self.item_a.pk, "quantity": 1}, {"item_id": self.item_b.pk, "quantity": 1}], "payment_method": "card", "tip_amount": "0"},
            ]), content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        closed = TableAccount.objects.filter(table=self.table, status=TableAccount.Status.CLOSED)
        self.assertEqual(closed.count(), 2)
        self.assertEqual(sorted(account.subtotal_closed for account in closed), [50, 80])

    def test_split_view_requires_a_responsible_waiter(self):
        response = self.client.post(
            reverse("tables:table_split_close", args=(self.account.pk,)),
            data=self.split_payload(responsible_waiter=""), content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("responsable", response.json()["error"])

    def test_split_view_requires_at_least_two_splits(self):
        response = self.client.post(
            reverse("tables:table_split_close", args=(self.account.pk,)),
            data=self.split_payload(splits=[
                {"items": [{"item_id": self.item_a.pk, "quantity": 1}, {"item_id": self.item_b.pk, "quantity": 1}], "payment_method": "cash", "tip_amount": "0", "cash_tendered": "80"},
            ]), content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)


class TableLooseProductVisibilityTests(TestCase):
    def setUp(self):
        self.waiter = get_user_model().objects.create_user(
            username="mesero_bolillo", password="test-password",
        )
        self.waiter.groups.add(Group.objects.get(name=WAITER))
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
            channel=DailyProductStock.Channel.TABLE, initial_quantity=20,
        )
        table = DiningTable.objects.create(name="Mesa bolillo", display_order=103)
        self.account = TableAccount.objects.create(
            table=table, assigned_waiter=self.waiter, opened_by=self.waiter,
        )
        self.client.force_login(self.waiter)

    def test_loose_product_is_visible_in_lunch_mode(self):
        session = self.client.session
        session["table_capture_mode"] = "lunch"
        session.save()

        response = self.client.get(reverse("tables:table_detail", args=(self.account.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.bread, response.context["daily_order_loose_products"])

    def test_loose_product_is_also_visible_in_breakfast_mode(self):
        session = self.client.session
        session["table_capture_mode"] = "breakfast"
        session.save()

        response = self.client.get(reverse("tables:table_detail", args=(self.account.pk,)))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.bread, response.context["daily_order_loose_products"])
