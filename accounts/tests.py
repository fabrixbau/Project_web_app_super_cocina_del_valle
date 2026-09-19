from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .quick_switch import LOCK_KEY, logged_in_today_ids
from .roles import ADMIN, WAITER


class AdministratorPinAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="admin_with_waiter_role",
            password="test-password",
        )
        self.user.groups.add(
            Group.objects.get_or_create(name=ADMIN)[0],
            Group.objects.get_or_create(name=WAITER)[0],
        )
        self.client.force_login(self.user)

    def test_administrator_does_not_see_quick_switch_control(self):
        response = self.client.get(reverse("internal_portal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Cambiar mesero")

    def test_administrator_cannot_use_quick_switch_screen(self):
        response = self.client.get(reverse("accounts:quick_switch"))

        self.assertRedirects(response, reverse("internal_portal:dashboard"))


class QuickSwitchDailyLoginTests(TestCase):
    """El cambio rápido ya no usa PIN. Cambiar hacia un mesero que ya inició
    sesión hoy en esta tablet es instantáneo; hacia uno que no, el mismo
    formulario pide su contraseña real como único inicio de sesión del día."""

    def setUp(self):
        waiter_group = Group.objects.get_or_create(name=WAITER)[0]
        self.ana = get_user_model().objects.create_user(username="ana", password="ana-password12")
        self.ana.groups.add(waiter_group)
        self.beto = get_user_model().objects.create_user(username="beto", password="beto-password12")
        self.beto.groups.add(waiter_group)
        self.login_url = reverse("login")
        self.switch_url = reverse("accounts:quick_switch")

    def _login(self, user, password):
        return self.client.post(self.login_url, {"user": user.pk, "password": password})

    def test_normal_login_registers_waiter_for_today(self):
        self._login(self.ana, "ana-password12")
        self.assertIn(self.ana.pk, logged_in_today_ids(self.client.session))

    def test_first_switch_to_a_waiter_today_requires_real_password(self):
        self._login(self.ana, "ana-password12")
        # Sin contraseña: rechazado y sigue operando Ana.
        response = self.client.post(self.switch_url, {"waiter_id": self.beto.pk, "next": "/app/mesas/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escribe tu contraseña")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.ana.pk)
        # Contraseña incorrecta: también rechazado.
        response = self.client.post(
            self.switch_url, {"waiter_id": self.beto.pk, "password": "incorrecta", "next": "/app/mesas/"},
        )
        self.assertContains(response, "no es correcta")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.ana.pk)
        # Contraseña correcta: cambia y queda registrado para hoy.
        response = self.client.post(
            self.switch_url, {"waiter_id": self.beto.pk, "password": "beto-password12", "next": "/app/mesas/"},
        )
        self.assertRedirects(response, "/app/mesas/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.beto.pk)
        self.assertEqual(logged_in_today_ids(self.client.session), {self.ana.pk, self.beto.pk})

    def test_second_switch_to_the_same_waiter_needs_no_password(self):
        self._login(self.ana, "ana-password12")
        self.client.post(
            self.switch_url, {"waiter_id": self.beto.pk, "password": "beto-password12", "next": "/app/mesas/"},
        )
        # Beto ya está operando; regresar a Ana no debe pedir nada más.
        response = self.client.post(self.switch_url, {"waiter_id": self.ana.pk, "next": "/app/mesas/"})
        self.assertRedirects(response, "/app/mesas/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.ana.pk)

    def test_idle_lock_redirects_to_quick_switch_screen(self):
        self._login(self.ana, "ana-password12")
        session = self.client.session
        session[LOCK_KEY] = True
        session.save()
        response = self.client.get("/app/mesas/")
        self.assertRedirects(response, f"{self.switch_url}?next=/app/mesas/", fetch_redirect_response=False)
