from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from config.printing import printable_item
from menu.egg import selected_egg
from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product
from tables.models import DiningTable, TableAccount
from tables.services import add_package_to_table

from .models import Order
from .services import add_internal_order_package, update_internal_package_extras


class EggExtraTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="egg_tester")
        plancha = Category.objects.create(name="Plancha")
        self.egg = Product.objects.create(category=plancha, name="Huevo revuelto", price=15)
        self.stock = DailyProductStock.objects.create(
            stock_type=DailyProductStock.StockType.FIXED, date=None, product=self.egg,
            channel=DailyProductStock.Channel.SHARED, is_tracked=True, initial_quantity=5,
        )
        self.menu = DailyMenu.objects.create(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED)
        self.package, _ = MealPackage.objects.update_or_create(
            package_type=MealPackage.PackageType.RUNNING,
            defaults={"name": "Comida corrida", "price_without_water": 70, "price_with_water": 80, "table_refill_price": 0},
        )

    def test_order_egg_is_charged_and_released_with_package(self):
        order = Order.objects.create(
            daily_number=994, operating_date=self.menu.date, order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=0, created_by=self.actor,
        )
        item = add_internal_order_package(
            order=order, package=self.package, daily_menu=self.menu, actor=self.actor,
            cleaned_data={"first_course": self.egg, "second_course": self.egg, "main_course": self.egg,
                          "chicken_piece": "", "with_water": False, "tortillas": "no", "bread": False,
                          "beans": "no", "quantity": 1, "customization_comment": "", "egg_product": self.egg},
        )
        self.assertEqual(item.unit_price, Decimal("85.00"))
        self.assertEqual(self.stock.available_quantity, 1)
        self.assertIn("Huevo revuelto", printable_item(item)["details"])
        update_internal_package_extras(
            order=order, item=item, actor=self.actor,
            cleaned_data={"with_water": False, "tortillas": False, "bread": False,
                          "beans": False, "customization_comment": "", "egg_product": None},
        )
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("70.00"))
        self.assertEqual(self.stock.available_quantity, 2)

    def test_table_egg_is_part_of_package_price(self):
        table = DiningTable.objects.create(name="Mesa huevo")
        account = TableAccount.objects.create(table=table, assigned_waiter=self.actor, opened_by=self.actor)
        item = add_package_to_table(
            account=account, package=self.package, daily_menu=self.menu, added_by=self.actor,
            cleaned_data={"first_course": None, "second_course": None, "main_course": None,
                          "chicken_piece": "", "with_water": False, "refill_extra": False,
                          "is_complete": False, "egg_product": self.egg},
        )
        self.assertEqual(item.unit_price, Decimal("85.00"))
        self.assertEqual(item.egg_name_snapshot, "Huevo revuelto")
        self.assertEqual(self.stock.available_quantity, 4)

    def test_only_the_two_egg_products_from_plancha_are_selectable(self):
        self.assertEqual(selected_egg(str(self.egg.pk)), self.egg)
        other = Product.objects.create(category=Category.objects.create(name="Otros"), name="Huevo revuelto", price=1)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            selected_egg(str(other.pk))
