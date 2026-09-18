# Estación de impresión (Dell + POS-80)

Los botones normales de cocina y cobro y la selección de cocina modificada crean trabajos en PostgreSQL. Solo el agente de esta carpeta imprime: consulta la cola por HTTPS, renderiza el ticket con Edge y manda una imagen ESC/POS a la cola USB de Windows `POS-80 (copy 1)`. No abre cuadros de impresión y no necesita que los celulares vean la impresora.

## Preparación (una sola vez)

1. En el servidor, crear un secreto aleatorio diferente de `DJANGO_SECRET_KEY` y añadir `PRINT_AGENT_TOKEN=<secreto>` al `.env` privado. Reiniciar `super-cocina` después. No incluir el secreto en Git ni enviarlo por chat.
2. En la Dell, confirmar que Edge, Python 3.12 y la impresora `POS-80 (copy 1)` funcionan bajo el usuario de Windows que ejecutará el agente.
3. Crear un entorno virtual exclusivo en la Dell, instalar `pip install -r requirements.txt` de esta carpeta. Playwright usa Edge instalado; no se requiere descargar Chromium aparte.
4. Configurar las variables de entorno de **ese usuario** (con `[Environment]::SetEnvironmentVariable(...,"User")` en PowerShell, o desde "Editar las variables de entorno del sistema"): `PRINT_AGENT_TOKEN` con el mismo secreto, `PRINT_SERVER_URL=https://supercocina.win` y, si cambia el nombre, `PRINT_PRINTER_NAME=POS-80 (copy 1)`.
5. Crear la Tarea Programada para que el agente arranque solo al iniciar sesión en Windows, sin volver a tocar PowerShell después. Desde PowerShell **como administrador**:

   ```powershell
   $action = New-ScheduledTaskAction `
       -Execute "C:\SuperCocina\print-agent\dell_agent\.venv\Scripts\python.exe" `
       -Argument "C:\SuperCocina\print-agent\dell_agent\agent.py" `
       -WorkingDirectory "C:\SuperCocina\print-agent\dell_agent"
   $trigger = New-ScheduledTaskTrigger -AtLogOn
   $settings = New-ScheduledTaskSettingsSet `
       -StartWhenAvailable `
       -RestartCount 100 `
       -RestartInterval (New-TimeSpan -Minutes 1) `
       -ExecutionTimeLimit ([TimeSpan]::Zero)
   Register-ScheduledTask `
       -TaskName "SuperCocina Print Agent" `
       -Action $action -Trigger $trigger -Settings $settings `
       -Description "Agente de impresión de Super Cocina del Valle" `
       -RunLevel Highest -Force
   ```

   Ajusta las rutas si tu instalación no vive en `C:\SuperCocina\print-agent\dell_agent`.

## Operación diaria (después de la preparación)

```text
Prender la Dell
     ↓
Windows inicia sesión → la Tarea Programada arranca agent.py solo
     ↓
El agente manda un latido cada 10 segundos al servidor, indicando si ve la POS-80
     ↓
Prender/conectar la POS-80
     ↓
El siguiente latido reporta la impresora conectada → el servidor la marca en línea
     ↓
Cualquier celular, tablet o computadora ya puede imprimir
```

No hace falta abrir PowerShell, activar el entorno virtual ni ejecutar `python agent.py` a mano en el uso diario; eso solo se hizo una vez durante la preparación. Si alguna vez reinstalas Windows o mueves la carpeta, repite el paso 5.

## Qué pasa si algo está apagado o desconectado

- El servidor **sólo permite crear un ticket de impresión si recibió un latido reciente (menos de ~25 segundos) reportando la impresora conectada**. Si la Dell está apagada, el agente no corre, o la POS-80 está desconectada, la app responde de inmediato "La impresora no está disponible ahora mismo" y **no guarda nada en la cola**: no hay comandas viejas esperando a que todo se reconecte.
- Cada ticket que sí alcanza a crearse tiene una vigencia de 90 segundos (`expires_at`). Si por mala suerte la impresora se desconecta justo después de crearse el ticket y antes de que el agente lo reclame, ese ticket se marca `expired` en vez de imprimirse tarde.
- El agente sigue corriendo (y sigue mandando latidos) aunque la POS-80 esté apagada; en cuanto vuelve a detectarla, el siguiente latido ya la reporta disponible sin reiniciar nada.
- En la interfaz, sólo aparece un aviso rojo cuando alguien intenta imprimir y la estación no está disponible; si todo funciona bien no se muestra ningún indicador permanente.

## Prueba y seguridad

- Enviar un solo ticket de prueba desde un celular. Verificar que la pantalla indique primero “enviado a la Dell” y luego “enviado a la impresora”, y que el papel salga de la POS-80.
- El estado “enviado a la impresora” significa que Windows aceptó el trabajo; no confirma que el papel haya salido. Si el agente se apaga después de reclamar un trabajo, ese trabajo queda en “En impresión” para evitar duplicarlo automáticamente; esto es distinto del caso de "nunca se creó" que ya cubre la verificación de latido de arriba.
- Un administrador puede revisar `/admin/print_station/printjob/` y `/admin/print_station/printstation/` (estado del latido) y reintentar manualmente un trabajo, **solo tras comprobar que no salió en papel**.
- El agente usa únicamente HTTPS saliente hacia la app; no hay que abrir puertos entrantes en la Dell ni compartir la impresora por la red.
- El ticket queda guardado como snapshot en la BD y puede incluir datos de clientes. Proteger los respaldos y limitar el acceso al admin.
