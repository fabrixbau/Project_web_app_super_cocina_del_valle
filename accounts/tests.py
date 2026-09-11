from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

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

    def test_administrator_does_not_see_pin_control(self):
        response = self.client.get(reverse("internal_portal:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Configurar PIN")
        self.assertNotContains(response, "Habilitar tablet")

    def test_administrator_cannot_open_pin_setup(self):
        response = self.client.get(reverse("accounts:quick_pin_setup"))

        self.assertRedirects(response, reverse("internal_portal:dashboard"))
