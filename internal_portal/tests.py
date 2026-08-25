# NOTA TEMPORAL PARA APRENDIZAJE:
# Estas pruebas simulan usuarios con distintos roles y visitan URLs reales. Su objetivo
# es demostrar que la seguridad vive en backend: se prueban accesos permitidos, respuestas
# 403 y el caso de un usuario autenticado sin rol operativo.
# Puedes borrar esta nota después de leerla.

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.roles import ADMIN, DELIVERY, ORDER_TAKER, WAITER


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
