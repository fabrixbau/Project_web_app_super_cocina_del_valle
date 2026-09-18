import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from orders.models import Order

from .models import PrintJob, PrintStation


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
        self.heartbeat_url = reverse("print_station:heartbeat")
        self.auth = {"HTTP_AUTHORIZATION": "Bearer test-only-secret"}
        # La mayoría de las pruebas necesita una estación en línea; las que
        # prueban el rechazo por estación apagada la dejan sin latido.
        PrintStation.objects.create(
            name="cocina", printer_available=True, last_heartbeat_at=timezone.now(),
        )

    def test_request_requires_user_and_creates_snapshot(self):
        payload = {"source_type": "order", "source_id": self.order.pk, "ticket_type": "payment"}
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        job = PrintJob.objects.get(pk=response.json()["job_id"])
        self.assertEqual(job.status, PrintJob.Status.PENDING)
        self.assertIsNotNone(job.expires_at)
        self.assertIn("PRUEBA", job.html)
        self.assertIn("thermal-ticket", job.html)
        status = self.client.get(reverse("print_station:status", args=(job.pk,)))
        self.assertEqual(status.json()["status"], PrintJob.Status.PENDING)

    def test_request_rejected_without_online_station(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: sin latido reciente (estación recién
        # creada sin heartbeat, o impresora apagada), no debe crearse ningún
        # PrintJob; el usuario debe ver el error de inmediato. Borra esta nota.
        PrintStation.objects.filter(name="cocina").update(last_heartbeat_at=None)
        self.client.force_login(self.user)
        payload = {"source_type": "order", "source_id": self.order.pk, "ticket_type": "payment"}
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertIn("no está disponible", response.json()["error"])
        self.assertFalse(PrintJob.objects.exists())

    def test_request_rejected_with_stale_heartbeat(self):
        stale = timezone.now() - timedelta(seconds=PrintStation.HEARTBEAT_TIMEOUT_SECONDS + 5)
        PrintStation.objects.filter(name="cocina").update(last_heartbeat_at=stale)
        self.client.force_login(self.user)
        payload = {"source_type": "order", "source_id": self.order.pk, "ticket_type": "payment"}
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(PrintJob.objects.exists())

    def test_heartbeat_updates_station_and_gates_printing(self):
        PrintStation.objects.filter(name="cocina").update(last_heartbeat_at=None, printer_available=False)
        self.assertEqual(self.client.post(self.heartbeat_url).status_code, 401)
        response = self.client.post(
            self.heartbeat_url, data=json.dumps({"printer_available": True}),
            content_type="application/json", **self.auth,
        )
        self.assertEqual(response.status_code, 200)
        station = PrintStation.current()
        self.assertTrue(station.printer_available)
        self.assertTrue(station.is_online)
        # Con el latido registrado, ahora sí se puede encolar un ticket.
        self.client.force_login(self.user)
        payload = {"source_type": "order", "source_id": self.order.pk, "ticket_type": "payment"}
        response = self.client.post(self.request_url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 201)

    def test_agent_authorization_claim_and_finish(self):
        job = PrintJob.objects.create(
            source_type="order", source_id=self.order.pk, ticket_type="kitchen",
            label="Pedido de prueba", html="<main>test</main>", requested_by=self.user,
            expires_at=timezone.now() + timedelta(seconds=90),
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

    def test_claim_expires_stale_jobs_instead_of_printing_them(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: un trabajo que alcanzó a crearse pero
        # cuya vigencia ya venció (el agente tardó en reconectar) no debe salir
        # impreso horas después; debe quedar como "expired". Borra esta nota.
        expired_job = PrintJob.objects.create(
            source_type="order", source_id=self.order.pk, ticket_type="kitchen",
            label="Comanda vieja", html="<main>vieja</main>", requested_by=self.user,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        fresh_job = PrintJob.objects.create(
            source_type="order", source_id=self.order.pk, ticket_type="kitchen",
            label="Comanda vigente", html="<main>vigente</main>", requested_by=self.user,
            expires_at=timezone.now() + timedelta(seconds=90),
        )
        response = self.client.post(self.claim_url, **self.auth)
        self.assertEqual(response.json()["job"]["id"], fresh_job.pk)
        expired_job.refresh_from_db()
        self.assertEqual(expired_job.status, PrintJob.Status.EXPIRED)

    def test_bad_request_cannot_queue(self):
        self.client.force_login(self.user)
        response = self.client.post(self.request_url, data=json.dumps({
            "source_type": "order", "source_id": self.order.pk, "ticket_type": "other"
        }), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PrintJob.objects.exists())
