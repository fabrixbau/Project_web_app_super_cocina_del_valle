from django.test import TestCase
from django.urls import reverse


class PublicPortalAccessTests(TestCase):
    def test_public_home_does_not_require_login(self):
        response = self.client.get(reverse("public_portal:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/app/")
