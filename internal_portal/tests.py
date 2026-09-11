# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas pruebas simulan usuarios con distintos roles y visitan URLs reales. Su objetivo
# es demostrar que la seguridad vive en backend: se prueban accesos permitidos, respuestas
# 403 y el caso de un usuario autenticado sin rol operativo.
# Puedes borrar esta nota después de leerla.

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER
from menu.inventory import adjust_stock, reserve_stock
from menu.models import Category, DailyProductStock, MealPackage, Product
from orders.models import Order, OrderItem


class InternalPortalAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_model = get_user_model()

    def login_as(self, role, username=None):
        user = self.user_model.objects.create_user(username=username or role.lower(), password="test-password")
        user.groups.add(Group.objects.get(name=role))
        self.client.force_login(user)
        return user

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("internal_portal:dashboard"))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("internal_portal:dashboard")}',
        )

    def test_authenticated_employee_can_open_dashboard(self):
        self.login_as(WAITER)
        response = self.client.get(reverse("internal_portal:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, WAITER)

    def test_profile_is_created_with_user(self):
        user = self.user_model.objects.create_user(username="empleado")
        self.assertEqual(user.profile.user_id, user.id)

    def test_authenticated_user_without_role_cannot_open_internal_portal(self):
        user = self.user_model.objects.create_user(username="sin-rol", password="test-password")
        self.client.force_login(user)
        response = self.client.get(reverse("internal_portal:dashboard"))
        self.assertEqual(response.status_code, 403)

    def test_waiter_can_open_tables_but_not_reports_or_deliveries(self):
        self.login_as(WAITER)
        self.assertEqual(self.client.get(reverse("internal_portal:tables")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_portal:orders")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_portal:deliveries")).status_code, 403)
        self.assertEqual(self.client.get(reverse("internal_portal:reports")).status_code, 403)

    def test_order_taker_can_open_tables_orders_and_deliveries(self):
        self.login_as(ORDER_TAKER)
        for url_name in ("tables", "orders", "deliveries"):
            response = self.client.get(reverse(f"internal_portal:{url_name}"))
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_portal:reports")).status_code, 403)

    def test_delivery_user_can_only_open_deliveries(self):
        self.login_as(DELIVERY)
        self.assertEqual(self.client.get(reverse("internal_portal:deliveries")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_portal:tables")).status_code, 403)
        self.assertEqual(self.client.get(reverse("internal_portal:orders")).status_code, 403)
        self.assertEqual(self.client.get(reverse("internal_portal:reports")).status_code, 403)

    def test_administrator_can_open_every_section(self):
        self.login_as(ADMIN)
        for url_name in ("tables", "orders", "deliveries", "reports"):
            response = self.client.get(reverse(f"internal_portal:{url_name}"))
            self.assertEqual(response.status_code, 200)

    def test_superuser_can_open_every_section_without_group(self):
        user = self.user_model.objects.create_superuser(username="root", password="test-password")
        self.client.force_login(user)
        for url_name in ("dashboard", "tables", "orders", "deliveries", "reports"):
            response = self.client.get(reverse(f"internal_portal:{url_name}"))
            self.assertEqual(response.status_code, 200)


class SalesReportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="sales_admin", password="test-password")
        self.client.force_login(self.admin)
        category = Category.objects.create(name="Comida corrida")
        self.consomme = Product.objects.create(category=category, name="Consomé", price=20)
        self.rice = Product.objects.create(category=category, name="Arroz rojo", price=25)
        self.stew = Product.objects.create(category=category, name="Pollo con mole", price=45)
        self.package = MealPackage.objects.get(package_type=MealPackage.PackageType.RUNNING)

    def test_report_counts_finalized_packages_and_excludes_drafts(self):
        completed = Order.objects.create(
            daily_number=1, operating_date=timezone.localdate(), order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.PICKED_UP,
            customer_name="Mostrador", phone="", total=150,
        )
        completed_item = OrderItem.objects.create(
            order=completed, item_type=OrderItem.ItemType.PACKAGE, package=self.package,
            package_name_snapshot="Comida corrida", first_course=self.consomme,
            first_course_name_snapshot="Consomé", second_course=self.rice,
            second_course_name_snapshot="Arroz rojo", main_course=self.stew,
            main_course_name_snapshot="Pollo con mole", tortillas=True, beans=False,
            unit_price=75, quantity=2, subtotal=150,
        )
        stock = DailyProductStock.objects.create(
            date=timezone.localdate(), product=self.consomme,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=10,
        )
        adjust_stock(stock=stock, quantity=10, actor=self.admin, note="Segunda preparación")
        adjust_stock(stock=stock, quantity=15, actor=self.admin, note="Tercera preparación")
        reserve_stock(
            stock=stock, quantity=2, actor=self.admin,
            reference_type="order_item", reference_id=completed_item.pk,
        )
        draft = Order.objects.create(
            daily_number=2, operating_date=timezone.localdate(), order_type=Order.OrderType.PICKUP,
            source=Order.Source.INTERNAL, status=Order.Status.DRAFT,
            customer_name="Mostrador", phone="", total=45,
        )
        OrderItem.objects.create(
            order=draft, item_type=OrderItem.ItemType.PRODUCT, product=self.stew,
            product_name_snapshot="Pollo con mole", tortillas=False, beans=False,
            unit_price=45, quantity=1, subtotal=45,
        )

        response = self.client.get(reverse("internal_portal:reports"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["running_count"], 2)
        self.assertEqual(response.context["individual_total"], 0)
        self.assertEqual(response.context["totals"]["tickets"], 1)
        self.assertEqual(response.context["main_courses"][0]["name"], "Pollo con mole")
        self.assertEqual(response.context["main_courses"][0]["total"], 2)
        self.assertEqual(response.context["inventory_totals"]["prepared"], 35)
        self.assertEqual(response.context["inventory_totals"]["sold"], 2)
        self.assertEqual(response.context["inventory_totals"]["remaining"], 33)
