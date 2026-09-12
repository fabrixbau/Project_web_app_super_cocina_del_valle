import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.models import Order

from .models import PrintJob


@override_settings(PRINT_AGENT_TOKEN="test-only-secret")
class PrintQueueTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="print_admin", email="print@example.test", password="test-password"
        )
        self.order = Order.objects.create(
            daily_number=901, operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL,
            status=Order.Status.DRAFT, customer_name="Prueba", phone="", total=0,
            created_by=self.user,
        )
        self.request_url = reverse("print_station:request")
        self.claim_url = reverse("print_station:claim")
        self.auth = {"HTTP_AUTHORIZATION": "Bearer test-only-secret"}

    def test_request_requires_user_and_creates_snapshot(self):
        payload = {"source_type": "order", "source_id": self.order.pk, "ticket_type": "payment"}
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        job = PrintJob.objects.get(pk=response.json()["job_id"])
        self.assertEqual(job.status, PrintJob.Status.PENDING)
        self.assertIn("PRUEBA", job.html)
        self.assertIn("thermal-ticket", job.html)
        status = self.client.get(reverse("print_station:status", args=(job.pk,)))
        self.assertEqual(status.json()["status"], PrintJob.Status.PENDING)

    def test_agent_authorization_claim_and_finish(self):
        job = PrintJob.objects.create(
            source_type="order", source_id=self.order.pk, ticket_type="kitchen",
            label="Pedido de prueba", html="<main>test</main>", requested_by=self.user,
        )
        self.assertEqual(self.client.post(self.claim_url).status_code, 401)
        response = self.client.post(self.claim_url, **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job"]["id"], job.pk)
        self.assertIsNone(self.client.post(self.claim_url, **self.auth).json()["job"])
        finish = reverse("print_station:finish", args=(job.pk,))
        response = self.client.post(finish, data=json.dumps({"status": "printed"}), content_type="application/json", **self.auth)
        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual(job.status, PrintJob.Status.PRINTED)
        self.assertIsNotNone(job.completed_at)

    def test_bad_request_cannot_queue(self):
        self.client.force_login(self.user)
        response = self.client.post(self.request_url, data=json.dumps({
            "source_type": "order", "source_id": self.order.pk, "ticket_type": "other"
        }), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PrintJob.objects.exists())
