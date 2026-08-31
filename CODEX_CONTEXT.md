# CODEX_CONTEXT — Super Cocina del Valle

> Archivo de contexto operativo para agentes de desarrollo.
> Debe mantenerse compacto, actualizado y orientado a evitar que el agente tenga que reconstruir el contexto completo del proyecto en cada sesión.

---

## 1. Proyecto

Nombre:

```text
Super Cocina del Valle
```

Tipo:

```text
Aplicación web Django + PostgreSQL
```

Proyecto de referencia:

```text
Suerte Café
```

Documento funcional principal:

```text
SUPER_COCINA_DEL_VALLE_BLUEPRINT.md
```

---

## 2. Objetivo actual

Construir Super Cocina del Valle reutilizando de forma inteligente el proyecto Suerte Café y agregando:

- portal público;
- pedidos web;
- mesas;
- roles operativos;
- menú diario;
- paquetes;
- stock;
- zonas de entrega;
- repartidores;
- propinas;
- caja;
- gastos;
- reportes;
- impresión térmica;
- notificaciones.

---

## 3. Regla principal de trabajo

Antes de implementar una funcionalidad importante:

1. leer `SUPER_COCINA_DEL_VALLE_BLUEPRINT.md`;
2. revisar la implementación equivalente en Suerte Café;
3. decidir si se reutiliza, adapta o reemplaza;
4. evitar duplicación innecesaria;
5. implementar;
6. ejecutar pruebas;
7. actualizar este archivo.

### Flujo didáctico acordado con el desarrollador

Para cada bloque de implementación:

1. Codex escribe el código y agrega al inicio de cada archivo nuevo o editado una nota temporal, con la sintaxis de comentario apropiada para ese tipo de archivo.
2. La nota explica en lenguaje de nivel junior qué se está modificando, para qué sirve el archivo y cómo participa en el bloque actual.
3. La nota debe identificarse claramente como temporal para que el desarrollador pueda borrarla después de leerla.
4. Codex ejecuta las verificaciones automatizadas pertinentes.
5. Al entregar el bloque, Codex indica rutas y pasos concretos para probarlo manualmente en el entorno local.
6. Se avanza al siguiente bloque después de que el desarrollador revise el comportamiento.

Las notas temporales no deben incluir secretos ni alterar el comportamiento de la aplicación.

---

## 4. Arquitectura acordada

```text
Una sola aplicación Django
Una sola base PostgreSQL
Dos superficies:

/app/     → sistema interno autenticado
/pedir/   → portal público sin login
```

No crear dos proyectos independientes salvo que exista una decisión explícita documentada posteriormente.

---

## 5. Roles

```text
ADMIN
WAITER
ORDER_TAKER
DELIVERY
PUBLIC_CUSTOMER
```

`PUBLIC_CUSTOMER` no es necesariamente un usuario Django autenticado.

---

## 6. Responsabilidades del pedido

Mantener separados:

```text
created_by
order_taker
assigned_waiter
delivery_person
```

No reducirlos a un solo campo `employee`.

---

## 7. Estado actual del desarrollo

```text
PHASE: Foundation implementation
STATUS: Django project bootstrapped and verified
```

Código implementado específicamente para Super Cocina del Valle:

```text
Django configuration, accounts/profile foundation, operational role migration,
authenticated internal portal, isolated public portal, base templates and tests.
```

---

## 8. Plan técnico de migración/reutilización

1. Crear una base Django nueva en el repositorio destino, conservando el patrón `config/`, templates globales, static/media y configuración por entorno.
2. Adaptar primero `accounts`: perfil, login, errores y layout; reemplazar los dos grupos actuales por roles operativos y permisos backend explícitos.
3. Adaptar `menu`: categorías, productos, opciones, envases, imágenes y configuración; extender después con horarios, menú diario, paquetes y stock.
4. Adaptar `orders` conservando snapshots, cálculo servidor, numeración diaria y servicios transaccionales; rediseñar responsabilidades, tipos, origen, estados, pagos y propinas antes de migrar vistas.
5. Añadir módulos acotados para mesas, entregas/zonas, notificaciones y operación financiera (caja/gastos), evitando separar servicios desplegables.
6. Montar rutas internas bajo `/app/` y crear el portal público bajo `/pedir/`, con vistas, permisos y templates separados.
7. Migrar pruebas reutilizables por módulo y agregar cobertura crítica de permisos, estados, concurrencia de stock, cancelación y aislamiento público.
8. Validar PostgreSQL, migraciones y regresiones en cada módulo antes de continuar al siguiente.

---

## 9. Funcionalidades principales pendientes

```text
[x] Estructura base del proyecto
[x] Autenticación interna (base)
[x] Roles y matriz inicial de acceso
[x] Portal interno (base protegida)
[x] Portal público (base anónima)
[ ] Mesas
[ ] Pedidos
[ ] Estados extendidos
[x] Menú fijo (categorías y productos validados manualmente)
[x] Menú diario y periodos
[ ] Paquetes
[ ] Productos configurables
[ ] Envases
[ ] Stock
[ ] Alertas de stock
[ ] Zonas de entrega
[ ] Pedidos web
[ ] Notificaciones internas
[ ] Repartidores
[ ] Propinas
[ ] Métodos de pago
[ ] Cambio en efectivo
[ ] Caja
[ ] Gastos
[ ] Reportes
[ ] Impresión térmica
[ ] Comanda
[ ] Ticket de cobro
[ ] Ticket cliente
[ ] Backups
[ ] Configuración de producción
[ ] Despliegue
```

---

## 10. Decisiones críticas vigentes

```text
Pedido público:
entra como Pendiente de confirmar.

Stock:
se descuenta al finalizar/crear pedido.
No se reserva al agregar al carrito.

Cancelación:
devuelve stock.

Direcciones:
usar calles y rangos precargados.
No usar Maps inicialmente.

Dirección fuera de zona:
permitir enviar pedido.
Marcar para revisión.

WhatsApp:
no debe ser requisito para que exista el pedido.
Notificación interna es obligatoria.
Integración automática pendiente.

Impresión:
nunca automática.
Requiere confirmación del usuario.

Impresora:
OFICHIDO POS-8360.

Mesas:
son entidades.

Mesa:
puede conservar una cuenta abierta.

Propina de mesa:
100% mesero.

Propina de entrega:
100% repartidor.

Métodos de pago:
efectivo, terminal, transferencia.

Pasarela:
no existe.
```

---

## 11. Cambios recientes

### Foundation

- Se añadieron `ServicePeriod`, `DailyMenu` y `DailyMenuItem`, además de clasificación funcional y periodos múltiples en `Product`.
- La migración `menu.0002_service_periods_and_daily_menu` crea Desayuno 08:00-13:00 y Comida 12:30-17:00.
- Se creó la administración de menús diarios con estados borrador, publicado y cerrado, componentes y agua del día.
- El catálogo público combina el menú publicado de hoy con productos fijos filtrados por el horario actual.
- El desarrollador validó manualmente y guardó en Git el bloque anterior de categorías/productos.
- Se implementó el primer bloque de menú: categorías, productos, imágenes, disponibilidad, filtros y CRUD administrativo.
- Se añadió catálogo público en `/pedir/menu/` que solo muestra productos disponibles.
- La administración `/app/menu/` quedó restringida a Administrador/superusuario.
- Por indicación del desarrollador no se crearon ni ejecutaron pruebas automáticas; el bloque espera validación manual.
- Se centralizaron roles y protección backend en `accounts/roles.py`.
- Se añadieron áreas provisionales protegidas para mesas, pedidos, repartos y reportes.
- El dashboard ahora muestra únicamente las secciones permitidas para cada rol.
- La suite aumentó a 10 pruebas, incluyendo accesos 403 por rol y superusuario.
- Se creó el proyecto Django desde cero con configuración PostgreSQL por entorno.
- Se crearon `accounts`, `internal_portal` y `public_portal`.
- Se añadieron perfil automático y grupos `Administrador`, `Mesero`, `Telefonista` y `Repartidor` mediante migraciones.
- Se separaron `/app/` (autenticado) y `/pedir/` (público), con templates independientes.
- Se añadieron cuatro pruebas de acceso, perfil y aislamiento básico.

### Initial

- Se creó el contexto inicial del proyecto.
- Se documentó la arquitectura funcional acordada.
- Aún no se ha iniciado implementación específica.

---

## 12. Archivos/modulos relevantes

```text
Suerte Café:
D:/github/work_space_shared/project_app_web_suerte_cafe/Project_web_app_suerte_cafe

Super Cocina del Valle:
D:/github/work_space_shared/project_app_web_super_cocina_del_valle

Django settings:
D:/github/work_space_shared/project_app_web_suerte_cafe/Project_web_app_suerte_cafe/config/settings.py

Orders:
D:/github/work_space_shared/project_app_web_suerte_cafe/Project_web_app_suerte_cafe/orders/

Products:
D:/github/work_space_shared/project_app_web_suerte_cafe/Project_web_app_suerte_cafe/menu/

Users:
D:/github/work_space_shared/project_app_web_suerte_cafe/Project_web_app_suerte_cafe/accounts/
```

Suerte Café usa Django 6.0.8, PostgreSQL vía `django-environ`, Pillow y psycopg. Sus apps son `accounts`, `menu` y `orders`; tiene templates globales y por app, static propio, media, URLs por app y manejadores 400/403/404/500.

---

## 13. Modelos relevantes

Actualizar conforme se implementen.

Confirmados como base reutilizable/adaptable de Suerte Café:

```text
Profile
Category
Product
ProductOptionGroup
ProductOption
PackagingType
BusinessSettings
DeliveryCustomer
DailyOrderCounter
Order
OrderItem
OrderPackagingItem
```

`OrderItem` conserva nombre, precio base/final y configuración como snapshots. Los servicios de pedidos usan `transaction.atomic` y `select_for_update` para numeración y edición; son una referencia útil, pero todavía no implementan stock.

Nuevos candidatos:

```text
Table
DailyMenu
DailyMenuSection
MealPackage
StockItem
StockMovement
DeliveryStreetRange
InternalNotification
ExpenseCategory
Expense
DailyCashRegister
```

Los nombres definitivos pueden cambiar.

Cuando cambien, actualizar aquí.

---

## 14. Riesgos técnicos actuales

```text
- concurrencia de stock;
- doble confirmación de pedido;
- permisos entre roles;
- aislamiento del portal público;
- impresión térmica desde aplicación web;
- sincronización entre pedidos web y panel interno;
- estados inválidos;
- cálculos históricos;
- asignación correcta de propinas.
- Suerte Café incluye un `db.sqlite3` local aunque settings apunta a PostgreSQL: no reutilizar esa base como fuente de arquitectura;
- los grupos actuales de Suerte Café (`Administrador`, `Usuario regular`) son insuficientes para los roles del Blueprint;
- las transiciones actuales de estado requieren endurecer reglas y permisos por rol.
```

---

## 15. Reglas de actualización de este archivo

Actualizar este documento después de:
- implementar un módulo importante;
- cambiar arquitectura;
- crear/migrar modelos;
- tomar una decisión importante;
- descubrir una limitación;
- resolver un riesgo importante;
- finalizar una etapa;
- cambiar el próximo objetivo.

Mantenerlo compacto.

No copiar logs completos.

No pegar código extenso.

No convertirlo en changelog exhaustivo.

---

## 16. Formato para cambios futuros

Usar este patrón:

```text
## Current status
...

## Last completed
- ...

## In progress
- ...

## Next
- ...

## Important decisions
- ...

## Known issues
- ...

## Relevant files
- ...
```

---

## Current status

Estructura fija 2+2+3 aplicada en PostgreSQL y validada manualmente con un menú completo publicado.

## Last completed

- Migración `menu.0003_fixed_daily_menu_structure` aplicada por el desarrollador.
- Menú diario completo 2+2+3 creado, guardado y publicado correctamente en validación manual.
- Entorno `.venv` reconstruido correctamente con Python 3.12 y dependencias instaladas.
- Base `super_cocina_del_valle` conectada y migraciones iniciales aplicadas en PostgreSQL 18.
- Matriz inicial de acceso implementada para Administrador, Mesero, Telefonista y Repartidor.
- 10 pruebas ejecutadas correctamente; no hay migraciones nuevas pendientes.
- Esqueleto Django y configuración segura por variables de entorno.
- Migraciones iniciales de perfil y roles operativos.
- Login y portal interno protegido bajo `/app/`.
- Portal público anónimo y separado bajo `/pedir/`.
- `check`, revisión de migraciones y 4 pruebas ejecutadas correctamente.

## In progress

- Ninguno; el bloque de menú diario quedó aprobado.

## Next

- Modelar comida corrida y comida ejecutiva con variantes con/sin agua.
- Incorporar precios, tortillas, frijoles y refill de mesa en la configuración de paquetes.
- Después de aprobación, modelar comida corrida/ejecutiva y sus variantes de precio.
- Crear el primer superusuario administrador.

## Important decisions

- Ver sección 10.
- El desarrollo se realizará por bloques pequeños con notas didácticas temporales al inicio de cada archivo tocado, pruebas automatizadas y una guía de verificación manual al finalizar.

### Decisión confirmada: menú operativo y paquetes

- Mantener un catálogo único de `Product`; no crear modelos distintos para desayuno, corrida, ejecutiva y órdenes.
- Separar `Product` (qué se vende/cocina) de `DailyMenu` (qué está disponible hoy) y `MealPackage` (cómo se combinan componentes y se cobra).
- `DailyMenu` tiene exactamente siete lugares: 2 primeros tiempos, 2 segundos tiempos y 3 guisados.
- Primer tiempo: consomé de pollo fijo + una opción variable.
- Segundo tiempo: exactamente 2 opciones distintas entre arroz rojo/blanco y espagueti rojo/blanco.
- Tercer tiempo: exactamente 1 guisado de pollo + 1 de res + 1 variado.
- Clasificar componentes por función reutilizable: sopa/consomé/crema, segundo tiempo, guisado, plancha, bebida y complemento.
- Desayuno será una sección/productos con periodo 08:00-13:00; comida opera 12:30-17:00 y ambos se superponen de 12:30 a 13:00.
- Un producto puede pertenecer a varios periodos de servicio sin duplicarse; por ejemplo, huevos machacados puede venderse en desayuno y comida.
- Corrida y ejecutiva serán paquetes con pasos de selección. Corrida elige guisado; ejecutiva elige solo productos de plancha elegibles.
- “Con agua” y “sin agua” deben resolverse como variantes/precios del paquete, no duplicando todo el menú.
- Tortillas y frijoles serán complementos incluidos con preferencias explícitas para comandas externas; sin incremento de precio.
- Para mesa, el paquete con agua muestra 2/2 vasos incluidos sin registrar cada servicio. Una casilla `Refill extra` aplica un único cargo adicional a la partida; no existe contador de vasos. Para recoger/entrega incluye 1 vaso y no aplica refill.
- Solo existe un sabor de agua por día y se publica como parte del menú diario.
- Tortillas y frijoles deben preguntarse y guardarse explícitamente en cada paquete, sin costo adicional.
- La pieza pierna/muslo debe ser una opción requerida del guisado de pollo y, posteriormente, una unidad de stock independiente.
- La interfaz de mesero se plantea con dos vistas: mapa visual de mesas/cuenta activa e historial de órdenes del día/semana.

## Known issues

- Integración WhatsApp pendiente.
- Impresión POS-8360 pendiente de validar técnicamente.
- La matriz actual protege áreas generales; los permisos CRUD detallados se agregarán junto con cada módulo real.
- El módulo menú no fue validado automáticamente por decisión del desarrollador.
- Los nuevos periodos y menú diario tampoco tienen pruebas automáticas por decisión del desarrollador.
- Antes de crear 0003 se confirmó que existían 0 `DailyMenu` y 0 `DailyMenuItem`; retirar la tabla flexible no pierde datos operativos.

## Relevant files

```text
SUPER_COCINA_DEL_VALLE_BLUEPRINT.md
CODEX_CONTEXT.md
manage.py
config/settings.py
config/settings_test.py
config/urls.py
accounts/models.py
accounts/roles.py
accounts/migrations/0002_create_operational_roles.py
menu/models.py
menu/forms.py
menu/views.py
menu/urls.py
menu/migrations/0001_initial.py
menu/migrations/0002_service_periods_and_daily_menu.py
menu/migrations/0003_fixed_daily_menu_structure.py
menu/templates/menu/
internal_portal/
public_portal/
templates/
../project_app_web_suerte_cafe/Project_web_app_suerte_cafe/config/settings.py
../project_app_web_suerte_cafe/Project_web_app_suerte_cafe/config/urls.py
../project_app_web_suerte_cafe/Project_web_app_suerte_cafe/accounts/
../project_app_web_suerte_cafe/Project_web_app_suerte_cafe/menu/
../project_app_web_suerte_cafe/Project_web_app_suerte_cafe/orders/
```

## Actualización: paquetes de comida

- Se implementó `MealPackage` para corrida y ejecutiva con precio sin agua, con agua y cargo único de refill en mesa.
- La migración `menu.0004_meal_packages` crea y siembra ambos paquetes con precios iniciales en cero; está pendiente de aplicar.
- Se agregó configuración interna en `/app/menu/paquetes/` y acceso desde Administrar menú.
- Se agregó un armador público que usa el menú publicado 2+2+3: corrida elige guisado diario y ejecutiva solo plancha elegible.
- Tortillas y frijoles son respuestas obligatorias; refill solo es válido para mesa con agua.
- El armador únicamente calcula una vista previa y todavía no persiste órdenes.
- Este bloque queda pendiente de validación manual. No se agregaron ni ejecutaron pruebas automáticas por decisión del desarrollador.
- `/pedir/menu/` está destinado al cliente externo y solo ofrece recoger en la fonda o entrega a domicilio.
- El flujo público no muestra mesa, refill ni explicaciones sobre vasos; esas reglas quedan reservadas para la futura interfaz interna de meseros.

## Actualización: primer bloque de pedidos web

- Se creó la app `orders` con `Order`, `OrderItem` y `DailyOrderCounter`.
- Un paquete público ahora se guarda con estado `Pendiente de confirmar` y origen `Portal público`.
- El folio es consecutivo por día y se genera dentro de una transacción.
- La confirmación pública usa UUID para no exponer pedidos mediante identificadores consecutivos.
- Recoger exige nombre y teléfono; entrega añade calle, números, colonia y referencias.
- Se registran efectivo, terminal o transferencia; efectivo puede registrar monto y cambio.
- `OrderItem` conserva snapshots del paquete, tiempos, agua, complementos y precio.
- Este bloque guarda una sola partida. Carrito, productos individuales, stock, zonas, notificaciones y panel interno siguen pendientes.
- Migración `orders.0001_initial` pendiente de aplicar y bloque pendiente de validación manual.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.

## Actualización: identificación al recoger y panel interno

- Para recoger, el formulario pide nombre y apellido por separado y ambos son obligatorios.
- Para entrega, nombre es obligatorio y apellido opcional; el pedido sigue guardando el nombre completo en `customer_name`.
- La mejora visual dinámica de campos según modalidad y método de pago queda explícitamente pospuesta.
- `/app/pedidos/` reemplaza el placeholder con listado filtrable y detalle completo.
- Administrador y Telefonista pueden confirmar o cancelar un pedido pendiente.
- Mesero puede consultar lista y detalle, pero no recibe acciones de resolución.
- Resolver un pedido usa transacción y bloqueo; un pedido atendido no puede resolverse nuevamente.
- Los estados posteriores de preparación, listo, reparto y entrega quedan para bloques operativos posteriores.
- Este bloque queda pendiente de validación manual y no tuvo pruebas automáticas.

## Actualización: carrito público

- El carrito se guarda en sesión y no crea registros en base hasta completar checkout.
- Permite múltiples paquetes configurados, cantidades y productos individuales disponibles.
- Configuraciones idénticas y productos repetidos acumulan cantidad; configuraciones distintas permanecen separadas.
- El cliente puede actualizar cantidades de 1 a 20 y eliminar partidas.
- Datos de cliente, modalidad, dirección y pago se capturan una sola vez para todo el carrito.
- `OrderItem` ahora distingue `package` y `product`, conservando snapshots y subtotales de ambos.
- La migración `orders.0002_cart_order_items` amplía las partidas existentes de forma compatible y está pendiente de aplicar.
- Confirmación pública y detalle interno muestran múltiples partidas.
- Bloque pendiente de validación manual; no se ejecutaron pruebas automáticas.

## Actualización: notificaciones internas

- Se creó la app `notifications` y el modelo `InternalNotification` relacionado con `Order`.
- Cada checkout público exitoso crea una alerta `NEW_PUBLIC_ORDER` dentro de la misma transacción.
- Administrador y Telefonista ven un contador pendiente en la barra interna y acceden a `/app/notificaciones/`.
- La bandeja permite ver pendientes/todas, atender una alerta y abrir su pedido, o atender todas.
- La lectura es compartida por operación y registra fecha y empleado; Mesero y Repartidor no tienen acceso.
- Confirmar o cancelar directamente un pedido también atiende su notificación pendiente.
- Migración `notifications.0001_initial` pendiente de aplicar y bloque pendiente de validación manual.
- No se ejecutaron pruebas automáticas.

## Actualización: primer módulo de repartos

- `/app/repartos/` reemplaza el placeholder con un panel para todos los pedidos a domicilio, sin depender de su estado.
- Administrador, Telefonista y Repartidor pueden asignar cualquier pedido a un usuario activo del grupo Repartidor.
- Los tres roles pueden sustituir al repartidor responsable en cualquier momento; la última asignación queda registrada.
- La asignación usa bloqueo transaccional para evitar escrituras simultáneas inconsistentes.
- El pedido guarda repartidor, usuario que asignó y fecha/hora de asignación.
- Solo el repartidor asignado, Administrador o Telefonista pueden registrar la entrega como Entregado.
- Al reiniciar el ciclo se limpia la asignación anterior, pero se conserva el historial de estados.
- Los pedidos para recoger nunca aparecen en Repartos ni pueden asignarse.
- Migración `orders.0005_order_delivery_assignment` pendiente de aplicar y bloque pendiente de validación manual.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.
- La barra superior del portal interno identifica por nombre o username al usuario que mantiene la sesión activa.

## Actualización: mapa y cuentas base de mesas

- Se creó la app `tables` con las entidades `DiningTable` y `TableAccount`.
- PostgreSQL impide mediante restricción que una mesa tenga dos cuentas abiertas simultáneamente.
- `/app/mesas/` muestra un mapa físico adaptable: M1/M8, M2/M7, M3/M6, M4/M5 y M9 centrada al fondo.
- La migración `tables.0002_fixed_nine_table_map` crea/completa las nueve mesas y guarda fila/columna.
- Las mesas son botones grandes: verde para Disponible y terracota para Ocupada.
- Se retiró la creación escrita de mesas del panel cotidiano porque la fonda tiene nueve posiciones fijas.
- Mesero abre una mesa asignándosela a sí mismo; Administrador y Telefonista eligen un usuario activo con rol Mesero.
- Una cuenta conserva mesero responsable, empleado que la abrió y fecha/hora.
- Mesero y Administrador pueden reasignar una cuenta abierta a otro usuario con rol Mesero.
- En este bloque todavía no se capturan consumos ni se cierran/cobran cuentas.
- Migración `tables.0002_fixed_nine_table_map` pendiente de aplicar y bloque pendiente de validación manual.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.

## Corrección: anticipación y formularios de paquetes

- El horario de comida no bloquea corrida/ejecutiva pública: antes de la 1:00 p. m. se permite agendar y se muestra un aviso informativo.
- Los widgets RadioSelect ahora reciben explícitamente sus opciones; esto corrige formularios de mesa con etiquetas vacías.
- Tanto en portal público como en Mesas, pierna/muslo permanece oculto salvo que el tercer tiempo sea pollo.
- Al seleccionar pollo, pierna o muslo se vuelve obligatorio en navegador y continúa siendo obligatorio en Django.
- No se agregó migración nueva y no se ejecutaron pruebas automáticas.

## Actualización: captura rápida de consumos de mesa

- `administrador_prueba` dejó de pertenecer al grupo Mesero y ya no aparece como responsable seleccionable.
- Se reforzó el contraste de los botones Disponible/Ocupada del mapa.
- `TableAccountItem` conserva producto, nombre y precio snapshot, cantidad, subtotal, empleado y hora.
- El detalle de cuenta funciona como punto de venta: categorías, productos en botones y ticket lateral.
- Cada toque guarda inmediatamente el consumo y actualiza el ticket lateral mediante `fetch`, sin recargar ni mover el scroll.
- Tocar un producto ya registrado aumenta su cantidad; el ticket agrupa visualmente cualquier línea histórica duplicada.
- El ticket aparece al existir productos y muestra solo producto, cantidad, subtotal, artículos y total a cobrar.
- Los botones `−`, `+` y `×` actualizan el ticket también sin recargar.
- Las categorías son pestañas superiores; solo se muestra la lista de productos de la categoría seleccionada.
- `TableCommand` se conserva por compatibilidad con la migración aplicada, pero ya no participa en el flujo cotidiano.
- El backend recalcula subtotales, bloquea la cuenta durante cambios y rechaza productos fuera de horario/no disponibles.
- Solo se incorporaron productos individuales; corrida/ejecutiva se integrarán después con su selector completo.
- Este ajuste no agrega migración nueva; requiere tener aplicadas las migraciones existentes hasta `tables.0004`.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.

## Actualización: paquetes en tickets de mesa

- Corrida y ejecutiva aparecen como botones destacados sobre las categorías cuando existe menú diario publicado.
- Cada botón abre un diálogo guiado sin abandonar la cuenta de mesa.
- Se reutiliza la validación 2+2+3: primer tiempo, segundo tiempo y guisado/plancha según paquete.
- Pieza de pollo, agua, tortillas y frijoles se validan explícitamente; refill extra solo permite activarse con agua.
- El precio de mesa usa con/sin agua y suma una sola tarifa de refill cuando corresponde.
- Una configuración idéntica incrementa cantidad; configuraciones diferentes permanecen en líneas distintas.
- El ticket muestra los tres tiempos como descripción y se actualiza con AJAX sin recargar.
- Migración `tables.0005_table_package_items` pendiente de aplicar y bloque pendiente de validación manual.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.

## Actualización: modalidad, pagos de entrega y ciclo repetible

- Antes de `/pedir/menu/` el cliente elige recoger o entrega; la modalidad se guarda en sesión y puede cambiarse.
- Pickup oculta domicilio y pago; exige nombre, apellido y teléfono, y conserva notas. El pago se define al llegar.
- Delivery exige domicilio y pago: terminal implica llevar el dispositivo físico, transferencia no requiere extras y efectivo permite billetes 50/100/200/500, monto personalizado o pago exacto.
- JavaScript controla visibilidad/exclusión de opciones de efectivo y Django repite todas las validaciones.
- Se agregó `Order.attention_started_by` y `attention_started_at`; abrir una notificación o realizar la primera transición registra al responsable.
- Se eliminó por completo `Atender todas`; cada alerta se atiende individualmente.
- Pickup: Pendiente → Confirmado → En preparación → Listo → Recogido.
- Delivery: Pendiente → Confirmado → En preparación → Listo → Entregado.
- Recogido y Entregado pueden reiniciar a Pendiente; el historial completo se conserva.
- Migración `orders.0004_order_attention_and_optional_payment` pendiente de aplicar y bloque pendiente de validación manual.
- No se ejecutaron pruebas automáticas.

## Actualización: flujo operativo e historial de estados

- Se agregó `Order.Status.PICKED_UP` (`Recogido`) y `OrderStatusHistory`.
- Flujo permitido: Pendiente → Confirmado → En preparación → Listo.
- Solo pickup continúa de Listo → Recogido; delivery queda en Listo hasta implementar asignación de repartidor.
- Pendiente también puede pasar a Cancelado; no se permiten saltos ni repeticiones.
- Cada transición usa bloqueo transaccional y registra estado anterior, nuevo, empleado y hora.
- Pedidos web nuevos registran su estado inicial como evento del Sistema.
- Administrador y Telefonista ven las acciones; Mesero conserva lectura sin botones.
- Pedidos anteriores no reciben historial inventado y comienzan a registrar desde su siguiente cambio.
- Migración `orders.0003_order_status_history` pendiente de aplicar y bloque pendiente de validación manual.
- No se ejecutaron pruebas automáticas.

## Mejora visual: formulario de productos

- Crear y editar productos ya no usa una lista plana de campos.
- La interfaz se divide en Información principal, Clasificación, Disponibilidad/venta y Horario para clientes.
- Disponible, venta por orden y elegibilidad ejecutiva se presentan como tarjetas con explicación y estado seleccionado visible.
- Los periodos de servicio aclaran que limitan el menú público, mientras Mesas conserva su regla interna sin filtro horario.
- El formulario conserva los mismos campos, validaciones y datos; este cambio no requiere migración.

## Mejora visual: armado público de paquetes

- `/pedir/menu/paquete/<tipo>/` presenta encabezado con precios, agua del día y aviso de pedido anticipado.
- Primer, segundo y tercer tiempo se muestran como pasos separados con opciones de radio visibles.
- Pierna/Muslo conserva su aparición condicional al elegir pollo.
- Agua, tortillas, frijoles y cantidad se agrupan en un bloque final antes de agregar al carrito.
- El ajuste es visual y adaptable; no cambia validaciones ni requiere migración.

## Actualización: cierre y cobro de cuentas de mesa

- Una cuenta abierta con consumos puede cobrarse completa mediante efectivo, terminal o transferencia.
- Este bloque no permite dividir una cuenta ni combinar métodos de pago.
- El cierre registra una fotografía de subtotal, propina, total pagado, empleado que cerró y hora.
- La propina se asigna 100% al mesero responsable que tenga la cuenta al momento de cerrarla.
- Efectivo permite marcar pago exacto o indicar monto recibido; el cambio se calcula y almacena.
- La interfaz ofrece únicamente billetes de $20, $50, $100, $200 y $500, como Suerte Café; aparecen al inicio y se ocultan si se elige Terminal o Transferencia.
- En el cierre de mesa, elegir un billete selecciona Efectivo automáticamente y muestra error inmediato si no cubre total más propina.
- Los métodos de pago se muestran en una sola fila; Terminal y Transferencia ocultan toda la sección de billetes.
- La propina se captura después del efectivo mediante botones de $5, $10, $15, $20, $25 y $30 o un monto manual.
- Billetes y propinas usan colores distintos para evitar confundir ambos importes.
- Los métodos de cierre se apilan como Efectivo, Transferencia y Terminal; se retiró el subtotal duplicado del encabezado.

## Terminología de pago presencial

- La versión 1 no procesa pagos en línea dentro de la aplicación.
- El método visible se llama `Terminal` para indicar que el personal debe llevar o usar una terminal física.
- El valor interno `card` se conserva para mantener compatibles pedidos y cuentas existentes.
- Las migraciones `orders.0006_rename_card_label_to_terminal` y `tables.0011_rename_card_label_to_terminal` actualizan el estado descriptivo sin transformar datos.

## Corrección: renovación diaria del menú en Mesas

- El contexto de la cuenta 38 confirmó que Corrida, Ejecutiva y Comida por orden se construyen con el `DailyMenu` publicado del 29/08.
- Mesas ya ignora periodos horarios; estos no explican que Comida por orden aparezca incompleta.
- El detalle de cuenta usa `never_cache` para impedir que el navegador reutilice el HTML operativo del día anterior.
- Las partidas ya agregadas conservan su menú histórico deliberadamente; el catálogo para nuevas partidas usa siempre el publicado hoy.
- La captura mostrada en la cuenta 38 estaba en `Modo desayunos` y exponía las categorías persistentes homónimas; por eso mezclaba productos históricos activos.
- `Comida corrida`, `Comida ejecutiva` y `Comida por orden` quedan excluidas del catálogo normal en ambos modos.
- Los tres accesos solo se renderizan en `Modo comida` y sus componentes se derivan exclusivamente del menú diario publicado hoy.

## Personalización de productos · bloque de configuración

- La personalización se diseña para ambos canales: `/pedir/menu/` y `/app/mesas/`.
- `ProductOptionGroup` organiza ingredientes por producto y admite elección única o múltiple, obligatoriedad y orden.
- `ProductOption` guarda nombre, cargo adicional, pertenencia a la preparación estándar, disponibilidad y orden.
- Un grupo de elección única solo permite una opción estándar; una opción estándar no puede quedar no disponible.
- Crear/editar producto contiene el editor completo de ingredientes en la misma pantalla; no se guarda opción por opción.
- Administración agrega varios grupos y todas sus filas de ingredientes antes de pulsar un solo `Guardar producto`.
- `Pegar grupo existente` también vive dentro del editor integrado y agrega una copia independiente al formulario actual.
- El navegador serializa la receta como JSON, pero Django valida nombres, tipos, estándares, disponibilidad y cargos antes de guardar.
- La sincronización transaccional conserva IDs existentes, crea filas nuevas y elimina solamente las retiradas del formulario.
- La migración `menu.0008_product_customization_groups` crea la base de configuración.
- La captura, snapshots, diferencias y etiqueta `Modificado` se conectan en el siguiente bloque después de validar esta administración.

## Personalización de productos · selectores público y Mesas

- `menu.selection.resolve_product_selection` es la regla compartida: valida pertenencia/disponibilidad, selección única, obligatoriedad y calcula cargos.
- La preparación estándar se preselecciona; quitar estándares o agregar alternativas produce diferencias `Sin ...` y `Agregar ...`.
- `/pedir/menu/` abre un diálogo antes de agregar productos configurables y conserva cantidad del formulario original.
- El carrito agrupa por producto + firma de opciones; configuraciones diferentes quedan en líneas distintas.
- Carrito, checkout y `OrderItem` usan precio base más cargos seleccionados.
- `/app/mesas/` usa el mismo diálogo para productos normales y Comida por orden; el pollo continúa después con Pierna/Muslo.
- El ticket agrupa por producto, pieza, candidato y firma; muestra `Modificado` y las diferencias debajo.
- Los candidatos automáticos de Corrida/Ejecutiva permanecen estándar porque después se sustituyen por una partida de paquete.
- `OrderItem` y `TableAccountItem` guardan JSON snapshot, firma y `is_customized` para conservar el historial.
- Migraciones: `orders.0007_order_item_customization` y `tables.0012_table_item_customization`.
- Productos existentes sin grupos mantienen el clic directo y el precio base.
- `ProductOption.replacement_pair` conecta alternativas equivalentes dentro de un grupo. Las opciones con la misma clave son excluyentes y el ticket expresa `Cambiar crema por mayonesa`.
- La migración `menu.0009_product_option_replacement_pair` agrega esta clave sin alterar las opciones existentes.
- La sincronización libera temporalmente nombres de grupos/opciones existentes antes de escribir el estado final; así pegar o renombrar no provoca `IntegrityError` por el orden intermedio de guardado.
- La biblioteca `/app/menu/ingredientes/` administra familias compartidas y muestra los productos asociados. Editar una familia sincroniza reglas, opciones, cargos y pares en todos ellos.
- `ProductOptionGroup.shared_key` identifica las réplicas técnicas de una familia; la migración `menu.0010_shared_ingredient_groups` une automáticamente configuraciones antiguas que sean exactamente iguales.
- Las tarjetas de producto en Mesas y `/pedir/menu/` muestran `−`, contador estándar, `+` y `Personalizar` dentro del cuerpo del recuadro, debajo de la imagen. Los cambios se envían por AJAX y no recargan la vista.
- El contador del catálogo suma solamente la firma estándar. Las configuraciones modificadas se agrupan por su propia firma y permanecen como partidas independientes.
- `change_item_in_ticket` incluye `configuration_signature` al aumentar/restar/eliminar, evitando que una acción sobre una receta modifique otras variantes.
- El selector `Personalizar` incluye un comentario opcional de hasta 150 caracteres. Se normaliza, forma parte de la firma y aparece entre paréntesis junto al nombre en carrito, ticket, confirmación e historial.
- `OrderItem.customization_comment` y `TableAccountItem.customization_comment` conservan la instrucción; migraciones `orders.0008` y `tables.0013`.
- La cuenta de mesa admite `customer_name` opcional (migración `tables.0014`), editable mientras está abierta y visible en encabezado, mapa e historial.
- `/app/mesas/historial/` conserva el periodo y permite combinar filtros `customer` (icontains) y `table` (nombre/número visible de mesa).
- El detalle de mesa busca exclusivamente en `Product.name`, sin distinguir acentos; oculta los descartados y ordena por relevancia: nombre inicia, una palabra inicia, nombre contiene. Los resultados reutilizan `−`, `+` y `Personalizar`.
- Los controles `−`, `+` y `×` son botones AJAX directos con URL/acción explícitas; ya no dependen de formularios dinámicos y bloquean únicamente la acción enviada mientras esperan respuesta.
- El servidor bloquea la cuenta, recalcula consumos y evita un cierre doble o con efectivo insuficiente.
- Al cerrar, la mesa vuelve a Disponible; la URL histórica conserva ticket y pago en solo lectura.
- La migración `tables.0006_table_account_payment` está pendiente de aplicar.
- No se crearon ni ejecutaron pruebas automáticas por decisión del desarrollador.

## Actualización: historial operativo de cuentas de mesa

- El mapa incorpora acceso a `/app/mesas/historial/` sin mezclar cuentas pasadas con las mesas activas.
- El filtro `Hoy` consulta cuentas abiertas durante la fecha operativa actual.
- `Esta semana` consulta desde el lunes hasta hoy.
- Mesero consulta solamente las cuentas donde figura como responsable; Administrador y Telefonista consultan todas.
- El resumen presenta cuentas encontradas, cuentas cerradas y total cobrado de las cerradas.
- Cada fila muestra mesa, apertura, mesero, estado, artículos y total, y permite abrir el detalle histórico.
- No se agregó migración para este bloque y no se ejecutaron pruebas automáticas.

## Actualización: mapa horizontal y apertura rápida

- Escritorio y tablet presentan M8, M7, M6, M5 y M9 arriba; M1, M2, M3 y M4 abajo.
- El mapa usa cinco columnas, dos filas y el alto disponible para evitar scroll en esas pantallas.
- Administrador y Telefonista ya no usan selector: cada mesero activo aparece como botón visible dentro de una mesa disponible.
- Tocar el nombre abre la cuenta y asigna ese mesero en una sola operación.
- Mesero conserva el flujo directo: abrir una mesa la asigna automáticamente a su usuario.
- La lista de botones admite más meseros en el futuro mediante ajuste automático.
- La migración `tables.0007_horizontal_table_map` está pendiente de aplicar.
- El diseño específico para celular queda pospuesto por decisión del desarrollador.
- No se ejecutaron pruebas automáticas.

## Actualización incremental: modos de captura de mesas

- `/app/mesas/` y el detalle de cuenta muestran un switch `Modo desayunos ↔ Modo comida`.
- Sin override, 07:00–12:59 usa desayuno y 13:00–06:59 usa comida con hora local de Django.
- El override manual se guarda por usuario/navegador en sesión y afecta el siguiente detalle de cuenta visitado.
- Cambiar el modo no modifica cuentas, productos ni periodos reales de disponibilidad.
- `Category` incorpora orden y visibilidad configurables separados para desayuno y comida.
- `show_table_packages` permite marcar la categoría que revelará corrida/ejecutiva al seleccionarla durante desayuno.
- En comida, los accesos a corrida/ejecutiva permanecen priorizados arriba del catálogo cuando existe menú publicado.
- La migración `menu.0005_table_category_modes` está pendiente de aplicar.
- Comidas incompletas, edición desde ticket, bloqueo de cierre y Comida por orden se implementaron en incrementos posteriores.
- No se ejecutaron pruebas automáticas.

## Actualización incremental: comidas de mesa progresivas

- `TablePackageForm` de Mesas ya no muestra ni exige tortillas ni frijoles; los flujos públicos conservan sus propios campos.
- Primer, segundo y tercer tiempo son opcionales al agregar corrida o ejecutiva a una mesa.
- `TableAccountItem` guarda referencias opcionales a los tres productos además de snapshots e indicador `is_complete`.
- Una comida sin los tres tiempos se muestra en el ticket con texto `Pendiente` y nombres de tiempos faltantes.
- Tocar una comida del ticket reabre el formulario compartido con sus selecciones guardadas.
- Guardar cambios actualiza tiempos, pieza de pollo, agua, refill, precio y subtotal bajo bloqueo transaccional.
- `close_table_account` rechaza en backend cualquier cuenta con paquetes incompletos e identifica sus nombres antes de procesar el pago.
- Se eliminó la confirmación JavaScript adicional al cobrar; el POST conserva todas las validaciones backend.
- La migración `tables.0008_progressive_table_packages` está pendiente de aplicar.
- `Comida por orden` construida desde menú diario quedó implementada en el incremento siguiente.
- No se ejecutaron pruebas automáticas.

## Actualización incremental: Comida por orden

- En Modo comida aparece al final una sección virtual `Comida por orden`; no requiere crear una categoría duplicada.
- Se construye, en orden, con consomé/primera opción, dos segundos tiempos y tres guisados del `DailyMenu` publicado de hoy.
- Solo muestra componentes activos, disponibles en su periodo y marcados `Se puede vender por orden`.
- Cada componente usa su precio individual de `Product` y se agrega al ticket común como producto snapshot.
- Sin menú publicado se muestra un aviso y no se ofrecen productos.
- Un endpoint específico bloquea el menú y valida pertenencia antes de reutilizar la suma transaccional de productos.
- Cambiar el menú invalida intentos posteriores de agregar componentes viejos mediante URL.
- Este incremento no agrega migración y no ejecuta pruebas automáticas.

## Corrección: paquetes abiertos entre días

- Cada paquete de mesa guarda ahora el `DailyMenu` que originó sus opciones.
- Una cuenta abierta ayer reabre corrida/ejecutiva usando el menú de ayer, no el publicado hoy.
- El detalle genera formularios históricos por partida y muestra la fecha del menú original.
- La edición permite completar una partida aunque el menú original ya esté cerrado o exista uno nuevo.
- Partidas anteriores intentan enlazarse por la fecha local de `added_at`; si faltaba vínculo, editarlo lo guarda.
- La migración `tables.0009_table_item_daily_menu` está pendiente de aplicar.
- No se ejecutaron pruebas automáticas.

## Actualización incremental: armado automático de comidas en mesa

- En Modo comida existen tres secciones virtuales derivadas del `DailyMenu` publicado: `Comida corrida`, `Comida ejecutiva` y `Comida por orden`.
- Corrida muestra los dos primeros tiempos, los dos segundos tiempos y los tres guisados del día.
- Ejecutiva muestra los primeros y segundos tiempos del día, más productos de plancha activos y elegibles para comida ejecutiva.
- Cada clic de Corrida/Ejecutiva entra como `is_package_candidate=True` mientras falte algún tiempo; no se mezcla con productos de Comida por orden.
- Al reunir primer + segundo + guisado, el backend consume una unidad de cada orden y crea una comida corrida sin agua.
- Al reunir primer + segundo + plancha elegible, realiza la misma sustitución por comida ejecutiva sin agua.
- En Comida corrida y Comida por orden, tocar pollo abre un diálogo rápido con Pierna/Muslo antes de registrar el clic.
- La pieza queda en la orden individual o pasa al paquete automático, incluso si el pollo se eligió antes que los demás tiempos.
- El formulario completo de paquete conserva su selector de pieza como alternativa y para futuras ediciones.
- Los botones originales de paquete permanecen como el segundo método para crear corrida o ejecutiva.
- `Comida por orden` conserva su endpoint aislado y nunca participa en la conversión.
- Cerrar una cuenta queda bloqueado si aún contiene candidatos de paquete; deben completarse o eliminarse.
- Los candidatos de paquete no requieren `is_sold_individually`; por eso una plancha elegible puede aparecer en Ejecutiva aunque no se venda por orden.
- Corrida/Ejecutiva tampoco aplican el periodo individual: mientras el menú de hoy siga publicado, muestran sus componentes activos y permiten completar el paquete.
- Todo `/app/mesas/` ignora periodos horarios: categorías normales y Comida por orden siguen exigiendo `is_sold_individually=True`, pero permanecen capturables después de las 17:00.
- El corte horario se conserva exclusivamente en el flujo público `/pedir/menu/` para impedir nuevas compras de clientes después del cierre de venta.
- Para `Comida por orden`, pertenecer al `DailyMenu` publicado autoriza la venta en Mesas aunque `is_sold_individually` esté apagado; el origen permanece como orden y nunca como candidato.
- `DailyMenu.beans_order` permite elegir opcionalmente un producto tipo Complemento (por ejemplo `Orden de frijoles`) que solo se agrega a Comida por orden.
- La orden de frijoles no cuenta como primer, segundo ni tercer tiempo y nunca participa en corrida/ejecutiva.
- Los armados parciales viven en la sesión por usuario y cuenta; modificar cantidades manualmente limpia los armados pendientes para evitar cruces.
- La migración `tables.0010_table_item_package_candidate` agrega la separación de origen y está pendiente de aplicar.
- La migración `menu.0006_daily_menu_beans_order` agrega el complemento opcional y está pendiente de aplicar.
- No se ejecutaron pruebas automáticas.

## Actualización incremental: navegación interna por rol

- `base_internal.html` muestra accesos a módulos en la barra superior usando `internal_navigation_sections`.
- La barra y el dashboard comparten `internal_portal.navigation.SECTIONS` y la misma `SECTION_ROLE_MATRIX` usada por los decoradores backend.
- Administrador ve Mesas, Pedidos, Repartos, Reportes y Menú.
- Mesero ve Mesas y Pedidos; Telefonista ve Mesas, Pedidos y Repartos; Repartidor ve Repartos.
- La sección correspondiente a la URL actual queda resaltada y el nombre de la aplicación enlaza al panel interno.
- Notificaciones conserva su permiso independiente para Administrador y Telefonista.
- La cabecera se divide en dos niveles: identidad/cuenta arriba y navegación completa debajo.
- Los módulos usan verde medio con texto blanco; el módulo activo usa amarillo con texto oscuro y hover blanco.
- En tablet la cuenta baja a una fila propia; la navegación mantiene botones grandes y desplazamiento horizontal si hiciera falta.
- Este cambio no agrega migración y no ejecuta pruebas automáticas.

## Actualización incremental: organizador visual de categorías

- `/app/menu/categorias/orden/` centraliza cinco órdenes: general, Cliente/Desayunos, Cliente/Comida, Mesas/Desayunos y Mesas/Comida.
- Los campos numéricos de orden se retiraron de `CategoryForm`; nombre, imagen y visibilidades siguen editándose individualmente.
- Cada panel presenta todas las categorías en su orden vigente y actualiza posiciones inmediatamente al arrastrar.
- Las flechas subir/bajar ofrecen una alternativa accesible; Pointer Events permiten arrastrar desde tablet.
- Categorías ocultas en un modo aparecen atenuadas pero continúan ordenables.
- La vista de comida representa Corrida/Ejecutiva como accesos fijos al inicio. `Comida por orden` es un acceso virtual, pero toma su posición de la tarjeta/categoría homónima dentro del orden configurable de Mesas · Comida.
- Un solo POST valida que las cinco listas contengan exactamente todas las categorías y guarda sus campos mediante `bulk_update` dentro de una transacción.
- Antes de las 12:30 `/pedir/menu/` usa orden/visibilidad de Cliente/Desayunos; desde las 12:30 usa Cliente/Comida.
- Categorías públicas ocultas se excluyen de la vista y el endpoint rechaza agregar por URL productos generales de una categoría oculta.
- Los dos paneles de Cliente incluyen checkbox `Mostrar`; cambia la previsualización de inmediato y guarda visibilidad junto con los cinco órdenes.
- Horarios, disponibilidad y cierre público continúan aplicándose además de la visibilidad de categoría.
- La migración `menu.0007_public_category_modes` copia el orden general a ambos modos públicos y los deja visibles inicialmente.
- No se ejecutaron pruebas automáticas.
# Cambio rápido de meseros en tablet compartida (2026-08-31)

- Cada mesero conserva su usuario y configura un PIN personal de 4 a 6 dígitos, almacenado con hash.
- Una tablet se habilita durante 12 horas usando la contraseña normal; cinco PIN erróneos bloquean el perfil cinco minutos.
- El cambio rápido autentica al usuario Django real y conserva la URL en la que se estaba trabajando.
- La tablet se bloquea tras tres minutos sin actividad y se desbloquea seleccionando un mesero con su PIN.
- El cambio voluntario se realiza en un desplegable de la barra superior; la pantalla completa queda reservada para una tablet bloqueada.
- El desplegable omite al operador actual: con un solo mesero alternativo lo preselecciona y pide solo su PIN; con varios muestra el selector.
- Los PIN son exclusivamente numéricos, admiten entre 1 y 10 dígitos y el campo recibe foco al abrir el desplegable.
- El PIN queda asociado permanentemente al perfil; un inicio de sesión normal crea una sesión confiable nueva sin obligar a definirlo otra vez.
- `TableAccount.assigned_waiter` sigue siendo el responsable y receptor de propina. `TableActivity.actor` registra quién ejecutó cada movimiento.
# Comentarios universales de productos

- Todos los productos individuales muestran `Personalizar`: con grupos permite editar ingredientes y comentario; sin grupos abre solamente el comentario.
- Los componentes de Corrida y Ejecutiva usan la misma tarjeta con menos, más y Personalizar, aunque conservan su función de completar automáticamente un paquete.
- Los formularios manuales de Corrida/Ejecutiva muestran los tres tiempos como bloques de opciones grandes, extras separados y confirmación fija al pie.
