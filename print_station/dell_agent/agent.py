"""Agente Windows para la POS-80. Ejecutar solo en la Dell conectada por USB."""

import io
import logging
import os
import time

import requests
import win32print
from PIL import Image
from playwright.sync_api import sync_playwright


SERVER = os.environ.get("PRINT_SERVER_URL", "https://supercocina.win").rstrip("/")
TOKEN = os.environ.get("PRINT_AGENT_TOKEN", "")
PRINTER = os.environ.get("PRINT_PRINTER_NAME", "POS-80 (copy 1)")
WIDTH_DOTS = 576


def render_ticket(html):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        try:
            page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=2)
            page.set_content(html, wait_until="load")
            ticket = page.locator(".thermal-ticket")
            ticket.wait_for(state="visible", timeout=10000)
            return ticket.screenshot(type="png")
        finally:
            browser.close()


def escpos_raster(png):
    image = Image.open(io.BytesIO(png)).convert("L")
    height = max(1, round(image.height * WIDTH_DOTS / image.width))
    image = image.resize((WIDTH_DOTS, height), Image.Resampling.LANCZOS)
    image = image.point(lambda pixel: 255 if pixel > 190 else 0, mode="1")
    row_bytes = WIDTH_DOTS // 8
    raster = bytes(value ^ 0xFF for value in image.tobytes())
    yield b"\x1b@"
    for start in range(0, height, 1024):
        rows = min(1024, height - start)
        yield b"\x1dv0\x00" + bytes((row_bytes & 255, row_bytes >> 8, rows & 255, rows >> 8))
        yield raster[start * row_bytes:(start + rows) * row_bytes]
    yield b"\n\n\n\x1dV\x00"


def print_ticket(png, job_id):
    printer = win32print.OpenPrinter(PRINTER)
    started = False
    try:
        win32print.StartDocPrinter(printer, 1, (f"Super Cocina #{job_id}", None, "RAW"))
        started = True
        win32print.StartPagePrinter(printer)
        for part in escpos_raster(png):
            win32print.WritePrinter(printer, part)
        win32print.EndPagePrinter(printer)
        win32print.EndDocPrinter(printer)
        started = False
    finally:
        if started:
            win32print.AbortPrinter(printer)
        win32print.ClosePrinter(printer)


def run():
    if not TOKEN:
        raise SystemExit("Falta PRINT_AGENT_TOKEN en la Dell.")
    if not SERVER.startswith("https://"):
        raise SystemExit("PRINT_SERVER_URL debe usar HTTPS.")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {TOKEN}"})
    logging.info("Escuchando %s para %s", SERVER, PRINTER)
    while True:
        try:
            response = session.post(f"{SERVER}/app/impresion/agente/tomar/", timeout=15)
            response.raise_for_status()
            job = response.json()["job"]
            if job is None:
                time.sleep(3)
                continue
            logging.info("Trabajo %s: %s", job["id"], job["label"])
            try:
                png = render_ticket(job["html"])
                print_ticket(png, job["id"])
                result = {"status": "printed"}
            except Exception as exc:
                logging.exception("Falló el trabajo %s", job["id"])
                result = {"status": "failed", "error": str(exc)[:500]}
            response = session.post(
                f"{SERVER}/app/impresion/agente/{job['id']}/finalizar/",
                json=result,
                timeout=15,
            )
            response.raise_for_status()
        except (requests.RequestException, KeyError, ValueError):
            logging.exception("Sin conexión con la cola; reintentando en 10 segundos")
            time.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
