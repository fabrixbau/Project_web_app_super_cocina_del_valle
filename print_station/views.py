import json
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET

from accounts.roles import ADMIN, ORDER_TAKER, WAITER, role_required
from config.printing import order_print_context, printable_item, table_print_context
from orders.models import Order
from tables.models import TableAccount

from .models import PrintJob, PrintStation

JOB_TTL_SECONDS = 90


def _snapshot(template, context):
    rendered = render_to_string(template, context)
    ticket = re.search(r'<main class="thermal-ticket[^\"]*">.*?</main>', rendered, re.S)
    if ticket is None:
        raise ValueError("No se pudo preparar el ticket de impresión.")
    css = (settings.BASE_DIR / "static" / "css" / "print-ticket.css").read_text(encoding="utf-8")
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<style>' + css + '\nbody{margin:0;padding:0;background:#fff}'
        '.thermal-ticket{margin:0;min-height:0;box-shadow:none}'
        '</style></head><body>' + ticket.group(0) + '</body></html>'
    )


def queue_ticket(*, source_type, source, ticket_type, items, user):
    # NOTA TEMPORAL PARA APRENDIZAJE: si la estación no reporta un latido reciente
    # con la impresora conectada, no creamos el PrintJob. Antes cualquier intento
    # de imprimir se guardaba en la cola aunque nadie estuviera escuchando, y esos
    # trabajos salían todos juntos horas después cuando el agente volvía a conectarse.
    # Borra esta nota después de leerla.
    if not settings.PRINT_AGENT_TOKEN:
        raise ValueError("La estación de impresión aún no está configurada.")
    if not PrintStation.current().is_online:
        raise ValueError(
            "La impresora no está disponible ahora mismo. Verifica que la computadora "
            "y la impresora térmica estén encendidas y vuelve a intentar."
        )
    if source_type == "order":
        context = order_print_context(source)
        label = f"Pedido {source.formatted_number}"
    else:
        context = table_print_context(source)
        label = f"Mesa {source.table.name}"
    context["items"] = items
    template = "printing/kitchen_ticket.html" if ticket_type == "kitchen" else "printing/payment_ticket.html"
    return PrintJob.objects.create(
        source_type=source_type,
        source_id=source.pk,
        ticket_type=ticket_type,
        label=label,
        html=_snapshot(template, context),
        requested_by=user,
        expires_at=timezone.now() + timedelta(seconds=JOB_TTL_SECONDS),
    )


@require_POST
@role_required(ADMIN, WAITER, ORDER_TAKER)
def request_print(request):
    try:
        data = json.loads(request.body)
        source_id = int(data.get("source_id", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Solicitud inválida."}, status=400)
    source_type = data.get("source_type")
    ticket_type = data.get("ticket_type")
    if source_id < 1 or source_type not in {"order", "table"} or ticket_type not in {"kitchen", "payment"}:
        return JsonResponse({"ok": False, "error": "Tipo de ticket inválido."}, status=400)

    if source_type == "order":
        source = get_object_or_404(Order.objects.select_related("created_by", "delivery_person"), pk=source_id)
    else:
        source = get_object_or_404(TableAccount.objects.select_related("table", "assigned_waiter", "opened_by"), pk=source_id)
    try:
        job = queue_ticket(
            source_type=source_type, source=source, ticket_type=ticket_type,
            items=[printable_item(item) for item in source.items.all()], user=request.user,
        )
    except ValueError as error:
        return JsonResponse({"ok": False, "error": str(error)}, status=503)
    return JsonResponse({"ok": True, "job_id": job.pk, "status": job.status, "label": job.label}, status=201)


@require_GET
@role_required(ADMIN, WAITER, ORDER_TAKER)
@never_cache
def job_status(request, job_id):
    job = get_object_or_404(PrintJob, pk=job_id, requested_by=request.user)
    return JsonResponse({"status": job.status, "error": job.error})


def _authorized(request):
    configured = settings.PRINT_AGENT_TOKEN
    bearer = request.headers.get("Authorization", "")
    return bool(configured) and secrets.compare_digest(bearer, f"Bearer {configured}")


@csrf_exempt
@require_POST
@never_cache
def claim_job(request):
    if not _authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=401)
    now = timezone.now()
    # NOTA TEMPORAL PARA APRENDIZAJE: si un trabajo pasó más de JOB_TTL_SECONDS
    # pendiente (el agente se desconectó justo después de crearse, o tardó en
    # reconectar), lo marcamos expirado en vez de imprimirlo. Un ticket de hace
    # una hora ya no sirve, aunque en su momento sí había una impresora disponible.
    # Borra esta nota después de leerla.
    PrintJob.objects.filter(status=PrintJob.Status.PENDING).filter(
        Q(expires_at__isnull=True) | Q(expires_at__lt=now)
    ).update(status=PrintJob.Status.EXPIRED)
    with transaction.atomic():
        job = PrintJob.objects.select_for_update(skip_locked=True).filter(status=PrintJob.Status.PENDING).first()
        if job is None:
            return JsonResponse({"job": None})
        job.status = PrintJob.Status.PRINTING
        job.claimed_at = now
        job.save(update_fields=["status", "claimed_at"])
    return JsonResponse({"job": {"id": job.pk, "label": job.label, "ticket_type": job.ticket_type, "html": job.html}})


@csrf_exempt
@require_POST
@never_cache
def agent_heartbeat(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: el agente de la Dell llama este endpoint
    # cada pocos segundos, esté o no la impresora física prendida, para que el
    # servidor sepa si puede aceptar nuevas impresiones. Sin latido reciente (o
    # con la impresora reportada como apagada), queue_ticket rechaza el trabajo
    # antes de guardarlo. Borra esta nota después de leerla.
    if not _authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=401)
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, TypeError, json.JSONDecodeError):
        data = {}
    station = PrintStation.current()
    station.printer_available = bool(data.get("printer_available"))
    station.last_heartbeat_at = timezone.now()
    station.last_error = str(data.get("error", ""))[:500]
    station.save(update_fields=["printer_available", "last_heartbeat_at", "last_error"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
@never_cache
def finish_job(request, job_id):
    if not _authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=401)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "JSON inválido."}, status=400)
    status = data.get("status")
    if status not in {PrintJob.Status.PRINTED, PrintJob.Status.FAILED}:
        return JsonResponse({"error": "Estado inválido."}, status=400)
    with transaction.atomic():
        job = get_object_or_404(PrintJob.objects.select_for_update(), pk=job_id)
        if job.status != PrintJob.Status.PRINTING:
            return JsonResponse({"error": "El trabajo ya no está en impresión."}, status=409)
        job.status = status
        job.completed_at = timezone.now()
        job.error = str(data.get("error", ""))[:500] if status == PrintJob.Status.FAILED else ""
        job.save(update_fields=["status", "completed_at", "error"])
    return JsonResponse({"ok": True, "status": job.status})
