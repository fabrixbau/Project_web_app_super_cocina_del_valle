from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class InternalPortalAccessTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("internal_portal:dashboard"))
        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("internal_portal:dashboard")}',
        )

    def test_authenticated_employee_can_open_dashboard(self):
        user = get_user_model().objects.create_user(username="mesero", password="test-password")
        user.groups.add(Group.objects.get(name="Mesero"))
        self.client.force_login(user)
        response = self.client.get(reverse("internal_portal:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mesero")

    def test_profile_is_created_with_user(self):
        user = get_user_model().objects.create_user(username="empleado")
        self.assertEqual(user.profile.user_id, user.id)
