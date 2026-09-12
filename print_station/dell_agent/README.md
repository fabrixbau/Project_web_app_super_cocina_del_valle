# Estación de impresión (Dell + POS-80)

Los botones normales de cocina y cobro y la selección de cocina modificada crean trabajos en PostgreSQL. Solo el agente de esta carpeta imprime: consulta la cola por HTTPS, renderiza el ticket con Edge y manda una imagen ESC/POS a la cola USB de Windows `POS-80 (copy 1)`. No abre cuadros de impresión y no necesita que los celulares vean la impresora.

## Preparación

1. En el servidor, crear un secreto aleatorio diferente de `DJANGO_SECRET_KEY` y añadir `PRINT_AGENT_TOKEN=<secreto>` al `.env` privado. Reiniciar `super-cocina` después. No incluir el secreto en Git ni enviarlo por chat.
2. En la Dell, confirmar que Edge, Python 3.12 y la impresora `POS-80 (copy 1)` funcionan bajo el usuario de Windows que ejecutará el agente.
3. Crear un entorno virtual exclusivo en la Dell, instalar `pip install -r requirements.txt` de esta carpeta. Playwright usa Edge instalado; no se requiere descargar Chromium aparte.
4. Configurar las variables de entorno de **ese usuario**: `PRINT_AGENT_TOKEN` con el mismo secreto, `PRINT_SERVER_URL=https://supercocina.win` y, si cambia el nombre, `PRINT_PRINTER_NAME=POS-80 (copy 1)`. Iniciar una terminal nueva para que recoja las variables.
5. Ejecutar `python agent.py` desde el entorno de la Dell. Dejarlo corriendo para la primera prueba. Para operación diaria, programar su inicio automático al iniciar sesión con el usuario propietario de la impresora.

## Prueba y seguridad

- Enviar un solo ticket de prueba desde un celular. Verificar que la pantalla indique primero “enviado a la Dell” y luego “enviado a la impresora”, y que el papel salga de la POS-80.
- El estado “enviado a la impresora” significa que Windows aceptó el trabajo; no confirma que el papel haya salido. Si el agente se apaga después de reclamar un trabajo, ese trabajo queda en “En impresión” para evitar duplicarlo automáticamente.
- Un administrador puede revisar `/admin/print_station/printjob/` y reintentar manualmente un trabajo, **solo tras comprobar que no salió en papel**.
- El agente usa únicamente HTTPS saliente hacia la app; no hay que abrir puertos entrantes en la Dell ni compartir la impresora por la red.
- El ticket queda guardado como snapshot en la BD y puede incluir datos de clientes. Proteger los respaldos y limitar el acceso al admin.
