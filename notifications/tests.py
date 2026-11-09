from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import WAITER
from menu.inventory import release_stock, reserve_stock
from menu.models import Category, DailyProductStock, Product

from .models import InternalNotification, StockAlert, StockAlertDismissal


class StockAlertTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Alertas de inventario")
        product = Product.objects.create(category=category, name="Sopa para alertas", price=20)
        self.stock = DailyProductStock.objects.create(
            date=timezone.localdate(), product=product,
            channel=DailyProductStock.Channel.TABLE,
            initial_quantity=11, low_stock_threshold=10,
        )
        self.first_user = get_user_model().objects.create_user(username="alerta_uno")
        self.second_user = get_user_model().objects.create_user(username="alerta_dos")
        waiter_group = Group.objects.get(name=WAITER)
        self.first_user.groups.add(waiter_group)
        self.second_user.groups.add(waiter_group)

    def test_alert_tracks_threshold_and_is_dismissed_per_user(self):
        reserve_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=1,
        )
        alert = StockAlert.objects.get(is_active=True)
        self.assertEqual(alert.available_quantity, 10)

        reserve_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=2,
        )
        alert.refresh_from_db()
        self.assertEqual(alert.available_quantity, 9)
        self.assertEqual(StockAlert.objects.filter(is_active=True).count(), 1)

        self.client.force_login(self.first_user)
        self.client.post(reverse("notifications:stock_alert_dismiss", args=(alert.pk,)))
        self.assertNotContains(self.client.get(reverse("notifications:notification_list")), "Sopa para alertas")

        self.client.force_login(self.second_user)
        self.assertContains(self.client.get(reverse("notifications:notification_list")), "Sopa para alertas")

    def test_restock_resolves_alert_and_new_drop_opens_a_new_one(self):
        reserve_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=1,
        )
        first_alert = StockAlert.objects.get(is_active=True)
        release_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=1,
        )
        first_alert.refresh_from_db()
        self.assertFalse(first_alert.is_active)

        reserve_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=2,
        )
        self.assertEqual(StockAlert.objects.filter(is_active=True).count(), 1)
        self.assertEqual(StockAlert.objects.count(), 2)

    def test_daily_alert_names_service_but_fixed_alert_does_not(self):
        reserve_stock(
            stock=self.stock, quantity=1, actor=self.first_user,
            reference_type="test", reference_id=1,
        )
        fixed_stock = DailyProductStock.objects.create(
            stock_type=DailyProductStock.StockType.FIXED,
            date=None,
            product=Product.objects.create(
                category=self.stock.product.category,
                name="Jugo permanente", price=25,
            ),
            channel=DailyProductStock.Channel.SHARED,
            initial_quantity=5,
            low_stock_threshold=5,
        )
        from .services import sync_stock_alert
        sync_stock_alert(fixed_stock)
        self.client.force_login(self.first_user)

        response = self.client.get(reverse("notifications:notification_list"))

        self.assertContains(response, "Quedan 10 de Sopa para alertas para Mesas")
        self.assertContains(response, "Quedan 5 de Jugo permanente")
        self.assertNotContains(response, "Jugo permanente para")


class MarkAllReadTests(TestCase):
    def setUp(self):
        from accounts.roles import ADMIN, ORDER_TAKER
        from orders.models import Order

        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="leer_todo_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.other_admin = user_model.objects.create_user(username="leer_todo_otro")
        self.other_admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.waiter = user_model.objects.create_user(username="leer_todo_mesero")
        self.waiter.groups.add(Group.objects.get_or_create(name=WAITER)[0])
        self.telefonista = user_model.objects.create_user(username="leer_todo_tel")
        self.telefonista.groups.add(Group.objects.get_or_create(name=ORDER_TAKER)[0])
        for number in (1, 2):
            order = Order.objects.create(
                daily_number=700 + number, operating_date=timezone.localdate(),
                order_type=Order.OrderType.PICKUP, customer_name="Web", phone="5500000000", total=50,
            )
            InternalNotification.objects.create(
                notification_type=InternalNotification.NotificationType.NEW_PUBLIC_ORDER,
                order=order, title=f"Pedido web {number}", message="Nuevo",
            )
        category = Category.objects.create(name="Leer todo")
        product = Product.objects.create(category=category, name="Sopa leer todo", price=20)
        stock = DailyProductStock.objects.create(
            date=timezone.localdate(), product=product, channel=DailyProductStock.Channel.TABLE,
            initial_quantity=5, low_stock_threshold=10,
        )
        self.alert = StockAlert.objects.create(stock=stock, available_quantity=5)

    def test_marks_orders_read_for_everyone_and_dismisses_alerts_only_for_me(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("notifications:notification_mark_all_read"))
        self.assertRedirects(response, reverse("notifications:notification_list"))
        self.assertFalse(InternalNotification.objects.filter(is_read=False).exists())
        notification = InternalNotification.objects.first()
        self.assertEqual(notification.read_by, self.admin)
        self.assertIsNotNone(notification.read_at)
        self.assertIsNone(notification.order.attention_started_at)
        self.assertTrue(StockAlertDismissal.objects.filter(alert=self.alert, user=self.admin).exists())
        self.assertFalse(StockAlertDismissal.objects.filter(alert=self.alert, user=self.other_admin).exists())

    def test_button_visible_for_admin_and_order_taker_only(self):
        for user, visible in ((self.admin, True), (self.telefonista, True), (self.waiter, False)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("notifications:notification_list"))
                if visible:
                    self.assertContains(response, "Marcar todas como leídas</button>")
                else:
                    self.assertNotContains(response, "Marcar todas como leídas</button>")

    def test_waiter_cannot_post_mark_all(self):
        self.client.force_login(self.waiter)
        self.client.post(reverse("notifications:notification_mark_all_read"))
        self.assertTrue(InternalNotification.objects.filter(is_read=False).exists())
