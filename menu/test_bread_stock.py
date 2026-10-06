from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product
from tables.models import DiningTable, TableAccount
from tables.services import add_package_to_table, add_product_to_table, change_item_in_ticket


class BreadStockTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="bread_stock_actor")
        self.bread = Product.objects.create(
            category=Category.objects.create(name="Comida por orden"),
            name="Bolillo", price=5, uses_bread_stock=True,
        )
        self.order_stock = DailyProductStock.objects.create(
            date=timezone.localdate(), item_kind=DailyProductStock.ItemKind.BREAD,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=2,
        )
        self.table_stock = DailyProductStock.objects.create(
            date=timezone.localdate(), item_kind=DailyProductStock.ItemKind.BREAD,
            channel=DailyProductStock.Channel.TABLE, initial_quantity=2,
        )
        table = DiningTable.objects.create(name="Mesa bolillo", display_order=101)
        self.account = TableAccount.objects.create(
            table=table, assigned_waiter=self.actor, opened_by=self.actor,
        )

    def test_table_package_uses_the_same_bread_supply_as_loose_sales(self):
        menu = DailyMenu.objects.create(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        package, _ = MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={"name": "Comida corrida", "price_without_water": 70, "price_with_water": 80, "table_refill_price": 10},
        )
        loose = add_product_to_table(account=self.account, product=self.bread, added_by=self.actor)
        package_item = add_package_to_table(
            account=self.account, package=package, daily_menu=menu, added_by=self.actor,
            cleaned_data={
                "first_course": None, "second_course": None, "main_course": None,
                "chicken_piece": "", "with_water": False, "refill_extra": False,
                "bread": True, "is_complete": False,
            },
        )
        self.assertTrue(package_item.bread)
        self.assertEqual(self.table_stock.available_quantity, 0)
        change_item_in_ticket(account=self.account, item=loose, action="remove", changed_by=self.actor)
        self.assertEqual(self.table_stock.available_quantity, 1)
        change_item_in_ticket(account=self.account, item=package_item, action="remove", changed_by=self.actor)
        self.assertEqual(self.table_stock.available_quantity, 2)
