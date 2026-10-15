from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN
from menu.models import Category, DailyMenu, DailyProductStock, Product
from orders.models import Order, OrderItem

from .models import DiningTable, TableAccount, TableAccountItem
from .services import change_item_in_ticket


class MenuChickenStockTests(TestCase):
    """Pollo cocido: pregunta pierna o muslo y descuenta del guisado de pollo del menú
    publicado de hoy, el que tenga más piezas de ese tipo en el canal (2026-10-15)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="pollo_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.client.force_login(self.admin)
        category = Category.objects.create(name="Comida por orden")
        self.mole = Product.objects.create(category=category, name="Pollo en mole", price=60,
                                           component_type=Product.ComponentType.CHICKEN_STEW, is_sold_individually=False)
        self.ciruela = Product.objects.create(category=category, name="Pollo a la ciruela", price=60,
                                              component_type=Product.ComponentType.CHICKEN_STEW, is_sold_individually=False)
        self.cooked = Product.objects.create(category=category, name="Pollo cocido", price=50, uses_menu_chicken_stock=True)
        today = timezone.localdate()
        self.menu = DailyMenu.objects.create(date=today, status=DailyMenu.Status.PUBLISHED)
        self.menu.set_stews([self.mole, self.ciruela])
        self.stocks = {}
        for channel in (DailyProductStock.Channel.TABLE, DailyProductStock.Channel.ORDERS):
            for product, legs in ((self.mole, 6), (self.ciruela, 3)):
                self.stocks[(channel, product.pk)] = DailyProductStock.objects.create(
                    date=today, daily_menu=self.menu, product=product, channel=channel,
                    chicken_piece=DailyProductStock.ChickenPiece.LEG, initial_quantity=legs,
                )
        table = DiningTable.objects.create(name="Mesa pollo", display_order=301)
        self.account = TableAccount.objects.create(table=table, assigned_waiter=self.admin, opened_by=self.admin)

    def available(self, channel, product):
        stock = self.stocks[(channel, product.pk)]
        stock.refresh_from_db()
        return stock.available_quantity

    def test_table_takes_leg_from_stew_with_more_pieces_and_returns_it(self):
        response = self.client.post(
            reverse("tables:table_daily_order_add", args=(self.account.pk, self.cooked.pk)),
            {"chicken_piece": "leg"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.available(DailyProductStock.Channel.TABLE, self.mole), 5)
        self.assertEqual(self.available(DailyProductStock.Channel.TABLE, self.ciruela), 3)
        self.assertEqual(self.available(DailyProductStock.Channel.ORDERS, self.mole), 6)  # Pedidos no se toca
        item = TableAccountItem.objects.get(account=self.account, product=self.cooked)
        self.assertEqual(item.chicken_piece, "leg")
        change_item_in_ticket(account=self.account, item=item, action="remove", changed_by=self.admin)
        self.assertEqual(self.available(DailyProductStock.Channel.TABLE, self.mole), 6)

    def test_table_requires_piece(self):
        response = self.client.post(
            reverse("tables:table_daily_order_add", args=(self.account.pk, self.cooked.pk)),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TableAccountItem.objects.filter(product=self.cooked).exists())

    def test_without_chicken_stew_in_menu_it_is_rejected(self):
        self.menu.set_stews([])
        response = self.client.post(
            reverse("tables:table_daily_order_add", args=(self.account.pk, self.cooked.pk)),
            {"chicken_piece": "leg"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("no tiene guisado de pollo", response.json()["error"])

    def test_orders_discount_from_orders_channel(self):
        order = Order.objects.create(
            daily_number=8100, operating_date=timezone.localdate(), order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT, customer_name="Cliente pollo",
            total=0, created_by=self.admin,
        )
        response = self.client.post(
            reverse("orders:internal_order_daily_product_add", args=(order.pk, self.cooked.pk)),
            {"chicken_piece": "leg"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.available(DailyProductStock.Channel.ORDERS, self.mole), 5)
        self.assertEqual(self.available(DailyProductStock.Channel.TABLE, self.mole), 6)  # Mesas no se toca
        self.assertEqual(OrderItem.objects.get(order=order, product=self.cooked).chicken_piece, "leg")

    def test_cards_ask_piece_and_use_menu_route(self):
        from django.template.loader import render_to_string

        table_card = render_to_string("tables/_catalog_product_card.html", {
            "product": self.cooked, "account": self.account, "daily_menu": self.menu, "daily_order": False,
        })
        self.assertIn("data-chicken-choice", table_card)
        self.assertIn(reverse("tables:table_daily_order_add", args=(self.account.pk, self.cooked.pk)), table_card)
        order = Order.objects.create(
            daily_number=8101, operating_date=timezone.localdate(), order_type=Order.OrderType.DELIVERY,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT, total=0, created_by=self.admin,
        )
        order_card = render_to_string("orders/_internal_product_card.html", {
            "product": self.cooked, "order": order, "daily_menu": self.menu, "daily_order": False,
        })
        self.assertIn("data-internal-chicken-choice", order_card)
        self.assertIn(reverse("orders:internal_order_daily_product_add", args=(order.pk, self.cooked.pk)), order_card)
