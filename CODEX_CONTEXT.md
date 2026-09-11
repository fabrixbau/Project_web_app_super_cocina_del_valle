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

### Corrección visual de paquetes en Mesas (08/09/2026)

- Los formularios de Comida corrida y Comida ejecutiva en Mesas muestran los tres tiempos con fotografías en una fila amplia.
- Agua y refill ya no compiten por el ancho de los tiempos.
- Cada formulario incluye una sección propia de Envases con imagen, precio y botones `− / +`; sus cantidades se agregan al ticket junto con el paquete.

### Rediseño del portal público `/pedir/menu/` (08/09/2026)

- La modalidad se elige mediante dos botones grandes: Recoger o Entrega a domicilio.
- El horario selecciona automáticamente Desayuno antes de las 12:31 y Comida desde las 12:31; el cliente no puede alternar manualmente estos modos.
- Comida abre con paquetes y menú diario en dos columnas; Desayuno muestra primero sus categorías y después permite adelantar comida con aviso de servicio posterior a la 1 p. m.
- Las categorías se navegan con botones y las imágenes agregan una unidad.
- El ticket público aparece al agregar la primera partida y permite sumar, restar, eliminar, editar complementos, agregar notas por producto y una nota general. También comparte el enfoque expandible de Mesas/Pedidos.
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
- Corrida y Ejecutiva manuales aceptan un comentario de cocina de hasta 150 caracteres; se conserva al editar y aparece entre paréntesis junto al nombre del paquete.
# Captura interna de pedidos

- Telefonista/Administrador crean folios persistentes desde `/app/pedidos/nuevo/` para recoger o entrega.
- Ambos tipos guardan forma de pago; entrega exige teléfono, domicilio y referencias. Efectivo registra pago exacto o monto para cambio.
- `requested_for` conserva la hora prometida y `created_by` al operador que originó el pedido.
- El buscador existente localiza por folio, nombre o teléfono y abre el editor para agregar productos posteriormente.
- El editor tiene switch Desayuno/Comida, categorías, controles rápidos, personalización universal y paquetes del menú diario.
- La captura empieza como `draft`: modalidad, menú, ticket y datos permanecen accesibles. Cerrar captura confirma y envía al listado, pero no bloquea ediciones.
- Recoger puede confirmarse sin pago; para marcarlo finalmente como recogido debe haberse registrado. Entrega exige pago al confirmar la captura.
## Ajuste del capturador interno de pedidos (2026-08-31)

- `/app/pedidos/<id>/editar/` comparte ahora la estructura visual de mesas: catálogo izquierdo y ticket fijo derecho.
- Guardar datos y cerrar captura viven dentro del ticket, pero envían el formulario único de cliente, domicilio, pago y notas.
- Las categorías virtuales Corrida, Ejecutiva y Comida por orden ya no se duplican con categorías normales.
- Terminal y transferencia ocultan el efectivo; pulsar un billete selecciona Efectivo automáticamente.
- Comida por orden valida y vende exclusivamente componentes del menú diario publicado.
- El ticket permanece fijo a la derecha durante la captura en computadora/tablet y tiene desplazamiento interno si acumula muchas partidas.
- `Guardar sin cerrar` acepta datos parciales; las obligaciones de domicilio y pago se exigen al cerrar la captura. Los errores de formulario ahora se anuncian claramente y conservan lo escrito.
- El rediseño POS usa una cuadrícula real: catálogo y controles a la izquierda, ticket `sticky` a la derecha sin superposición.
- La barra operativa concentra modalidad, panel desplegable de cliente y botones de Efectivo/Terminal/Transferencia. El efectivo despliega denominaciones y el ticket calcula el cambio.
- Telefonistas arma corrida/ejecutiva desde tarjetas `- / + / Personalizar`; cada primer+segundo+tercero forma un paquete independiente. `OrderItem.is_package_candidate` distingue tiempos pendientes y el cierre los rechaza.
- Agua, tortillas, frijoles y comentario configuran el siguiente paquete completado. El ticket separa `Cambio de` (efectivo recibido) y `Cambio` (importe a devolver).
- En captura interna, fecha/hora de entrega parten de la apertura del ticket y son editables. Recoger requiere nombre+fecha+hora; Entrega suma calle+número exterior. Teléfono, interior, colonia, referencias y notas son opcionales; colonia inicia como `del valle centro` en Entrega.
- Cliente/domicilio se autoguardan con debounce; los dos botones inferiores sólo retraen el panel. Un cierre inválido conserva la pantalla, resume errores y enfoca el primer campo.
- Paquetes internos exponen `Editar extras` para agua/tortillas/frijoles/comentario. Agregar el agua del día como bebida convierte el primer paquete sin agua y recalcula precio, en vez de duplicar el producto.
- La imagen de cualquier tarjeta agregable funciona como `+`. Extras bloquea sólo `OrderItem` antes de leer su paquete, evitando el `FOR UPDATE` sobre un outer join nullable de PostgreSQL.
## Validación visible al cerrar pedidos internos (2026-09-01)

- El formulario de `/app/pedidos/<id>/editar/` usa `novalidate` para que los campos HTML ocultos/retraídos no bloqueen silenciosamente el POST.
- Django conserva la validación autoritativa y muestra un resumen con cada dato faltante.
- Cuando hay errores, el panel del cliente se abre y la interfaz desplaza y enfoca el primer campo que debe corregirse.
- La imagen del producto conserva la acción de sumar una unidad, pero ya no muestra un distintivo `+` superpuesto.
- `Guardar sin cerrar` conserva el borrador y vuelve al listado; cerrar exige forma de pago tanto para Recoger como para Entrega.
- Los pedidos internos para Recoger nacen con cliente `Mostrador`; al enfocar ese campo se selecciona todo para reemplazarlo escribiendo directamente.
- Una solicitud con al menos una hora de anticipación cierra como `Programado`; una más cercana cierra como `En preparación`. Recoger termina en `Listo → Recogido`; domicilio usa `Listo → En reparto → Entregado`.
- El listado separa `Editar` de `Estado y seguimiento`; este último abre las transiciones disponibles y la bitácora. La captura también enlaza directamente al seguimiento.
- El tablero de pedidos ahora tiene encabezados, resumen de hasta tres partidas, domicilio, color de fila por modalidad y badge por estado. La fila abre el detalle y un botón avanza directamente al siguiente estado no destructivo.
- El avance de estado usa `fetch`: actualiza fila, badge y siguiente acción sin recarga ni pérdida de scroll. Los selectores filtran al cambiar y la búsqueda se envía tras 500 ms sin escribir; se eliminó el botón Filtrar.
- Recoger puede cerrar captura sin pago, pero `complete_pickup` exige definirlo. Entrega sigue exigiéndolo al cerrar. El AJAX incluye CSRF explícito y muestra errores en la fila; el clic de fila abre directamente `/editar/`.
- Corrección AJAX: el input `name="action"` ocultaba `HTMLFormElement.action` y generaba `/app/pedidos/[object HTMLInputElement]`; el fetch ahora lee la URL mediante `getAttribute("action")`.
- Los errores operativos incluyen enlace de recuperación: pago abre `/editar/#payment-methods`; repartidor abre Repartos filtrado por folio.
- Repartos usa un tablero único con filtros por texto/folio/dirección/cliente, estado y repartidor. Asignar o reasignar se hace con botones de nombres vía AJAX, sin recargar.
- Repartos se presenta como lista horizontal de filas altas. Sus transiciones `Listo → En reparto → Entregado` también son AJAX y conservan el scroll. Los contenedores de error respetan `hidden` y no dibujan bordes vacíos.
- El ticket interno usa flex: sólo las partidas hacen scroll y total/acciones permanecen visibles. Entregas con Terminal/Transferencia guardan propina separada, beneficiario, editor y fecha; Repartos permite montos rápidos o libre. En Mesas, clicar la imagen envía el mismo formulario que `+`.
- Corrección PostgreSQL en propinas: `update_delivery_tip` bloquea sólo `Order`; no combina `select_for_update()` con `select_related("delivery_person")` porque la FK nullable genera un outer join no bloqueable.
- La propina ya no tiene botón visible de guardado: montos rápidos guardan al instante y el libre usa debounce de 600 ms. En `/app/pedidos/<id>/editar/` aparece para Entrega + Terminal/Transferencia; el pago se autoguarda antes de permitir la propina.
- El folio visible combina `DDMM` con el consecutivo diario de tres posiciones: el primer pedido del 1 de septiembre es `0109001`. El consecutivo interno y su reinicio diario no cambian; los buscadores aceptan el folio compuesto.
- La agenda interna usa `Customer` y múltiples `CustomerAddress`. Al autoguardar una entrega completa se crea o actualiza la ficha enlazada al pedido; teléfono identifica al cliente cuando existe y nombre exacto sólo cuando está vacío. Telefonista/Admin pueden buscar, editar y seleccionar un domicilio para rellenar la captura.
- El alta manual muestra cliente y domicilio desde el inicio. El domicilio es opcional; si se empieza a llenar, calle y número exterior conservan su validación y ambos registros se crean juntos.
- En entregas internas, `Nombre del cliente` es el autocompletado de agenda; ya no existe un buscador separado. El teléfono se consulta normalizado y advierte el nombre duplicado con enlaces para revisar o reutilizar la ficha. `CustomerForm` repite la protección en backend.
- El autocompletado de Nombre se retrae al cambiar de campo. El autoguardado también devuelve la colisión telefónica, y la sincronización no escribe un teléfono sobre una ficha provisional si ya pertenece a otro contacto.
- `/app/pedidos/` desglosa Consumo, Propina y Total con propina cuando la entrega tiene propina registrada; sin propina evita repetir importes.
- El ticket interno permite editar una nota general de hasta 1000 caracteres y una nota por partida de hasta 150, sin reconstruir productos. Los botones grandes de Corrida/Ejecutiva vuelven a mostrarse sobre las categorías en modo comida.
- Los tickets laterales de Mesas y Telefonistas comparten `ticket-expand.js`: un clic sobre fondo/texto no interactivo amplía su columna y activa un fondo oscuro que bloquea el resto de la aplicación. Un segundo clic dentro del fondo blanco del ticket, un clic fuera de él o Escape restaura la vista; el clic exterior sólo cierra el enfoque y no activa controles subyacentes. Los controles internos del ticket continúan funcionando y no disparan la expansión.
- `/app/caja/` es un tablero exclusivo de Administrador para pedidos operativos. Prioriza entregas y permite buscar, asignar/reasignar repartidor, registrar Efectivo/Terminal/Transferencia y confirmar por separado que el cambio físico fue entregado al repartidor. Los pedidos para recoger aparecen en una sección secundaria sin asignación ni entrega de cambio.
- `Order.cash_settlement_confirmed`, `cash_settlement_by` y `cash_settlement_at` auditan la devolución/conciliación del cambio al final del día. Cambiar la forma de pago o el billete invalida esa confirmación para evitar conservar un movimiento obsoleto.
- `/app/caja/cambios/` reúne entregas en efectivo ya liberadas que requieren cambio. Filtra por periodo, repartidor y conciliación; muestra totales generales y por repartidor, y permite confirmar o corregir la devolución sin recargar.
- Confirmar una devolución en `/app/caja/cambios/` completa además el flujo del pedido hasta `Entregado`, usando las transiciones normales para conservar el historial. `/app/pedidos/` abre en `Activos` (sin Entregados, Recogidos ni Cancelados) y permite alternar a `Entregados y recogidos` o `Todos`.
- Caja, Cambios pendientes y Reporte de propinas tienen navegación cruzada. En Caja y Pedidos, domicilio usa azul y recoger naranja; los programados conservan su familia cromática con un tono más intenso. La superficie libre de cada fila de Caja abre la edición, mientras sus controles internos mantienen su propia acción.
- La diferencia programada usa fondo, borde grueso y etiqueta explícita con fecha/hora: azul intenso para domicilio y naranja intenso para recoger. La columna Cobro completa queda excluida de la navegación por fila y ya no se muestra `Abrir pedido`. `Otro $` inicia respuesta visual inmediata y reduce su espera de autoguardado a 250 ms.
- Caja consulta movimientos cada 7 segundos y reemplaza únicamente su región de pedidos, sin recargar la página ni mover el scroll. La sincronización se pospone si el usuario está escribiendo dentro de una fila o existe una operación de guardado en curso.
- Los filtros de Caja se aplican automáticamente y pueden combinar búsqueda libre, tipo de pedido, repartidor (incluido Sin asignar) y método de pago (incluido Sin definir).
- Caja maneja un estado propio mediante `cashier_released_at/by`: liberar retira inmediatamente la fila sin alterar Cocina/Reparto. Exige método y repartidor para domicilio, pero no confirmar la entrega/devolución de cambio. `Seguir orden` permite recuperar la última fila durante 3 segundos. El billete activo queda resaltado. La conciliación de cambio al final del día queda separada del despacho operativo.
- `/app/caja/propinas/` es exclusivo de Administrador y consolida propinas de mesas y repartos por periodo, tipo de responsable, persona y método. Efectivo se muestra únicamente como dato y queda fuera de `Total administrado`; éste suma sólo Terminal y Transferencia. Incluye indicadores globales, concentrado por empleado y detalle de movimientos.
- Cada movimiento del reporte de propinas abre bajo demanda un detalle modal del ticket correspondiente. Conserva filtros y scroll, bloquea el fondo y muestra cliente, responsable, domicilio, pago, importes, productos, modificaciones y notas; se cierra con `×`, Escape o clic en el fondo.
- El autocompletado de clientes permite seleccionar directamente el nombre (usa su primer domicilio) o un domicilio específico. Cada consulta lleva una versión lógica para ignorar respuestas atrasadas que lleguen después de una selección o búsqueda más reciente. Al seleccionar, Datos del cliente se retrae sin detener el autoguardado; elegir una forma de pago también lo retrae y Efectivo abre inmediatamente sus billetes.
- `/app/pedidos/` muestra el repartidor asignado junto al domicilio de cada entrega, o `Sin asignar` mientras esté pendiente. La consulta usa `select_related` para no generar una consulta adicional por fila.
- Caja reutiliza las transiciones e historial de Pedidos: cada fila muestra el estado y su siguiente paso (`Confirmar`, `Preparar`, `Listo`, `En reparto`, etc.). El avance ocurre por AJAX, conserva el scroll y mantiene las validaciones de pago, modalidad y repartidor.
- En entregas, Cobro de Caja muestra montos rápidos de propina para Terminal/Transferencia y un importe libre con autoguardado. Efectivo oculta el bloque y elimina la propina administrada; `$0` permite corregirla. Se actualizan propina y total con propina sin recargar.
- Los formularios manuales de Comida corrida y ejecutiva en la captura interna muestran fotografías seleccionables para sus tres tiempos. La Corrida queda limitada al menú diario; la Ejecutiva añade un buscador local por nombre que filtra primeros, segundos y opciones elegibles de plancha sin recargar.
- El selector manual de paquetes usa en escritorio tres columnas compactas para mantener los tiempos y acciones dentro de la pantalla. Agua, Tortillas Sí/No y Frijoles Sí/No comparten una fila y toda su superficie funciona como botón. La cantidad viaja oculta y fija en uno: cada envío crea un paquete independiente.
- Pierna/Muslo no existe visualmente en Comida ejecutiva. En Corrida inicia oculto y aparece sólo al seleccionar el producto exacto configurado como guisado de pollo del menú diario; cambiar de guisado limpia la pieza. Los Sí/No de tortillas y frijoles se renderizan explícitamente como botones táctiles grandes.
- Repartos aplica aislamiento por perfil: un Repartidor ve sólo entregas sin asignar o propias y únicamente puede autoasignarse; Administrador puede asignar/reasignar cualquiera y Telefonista/Mesero no pueden asignar. Las mismas restricciones se validan en backend.
- Un Repartidor no puede editar propina de pedidos ajenos ni después de `Entregado/Recogido`; Administrador y Telefonista conservan la gestión autorizada. El filtro de estados de `/app/repartos/` acepta múltiples estados mediante botones checkbox y ausencia de selección significa Todos.
- En captura interna, tanto Entrega como Recoger + Efectivo pueden cerrar sin billete, monto libre ni Pago exacto. Se guarda `cash_tendered=None` y las vistas operativas lo muestran como `Monto por definir`, sin confundirlo con pago exacto; si se proporciona denominación, conserva la validación y cálculo existentes.
- `Liberar de Caja` también completa atómicamente el flujo operativo: Recoger avanza por todas las transiciones hasta `Recogido`; Entrega avanza hasta `En reparto`. Cada estado intermedio se conserva en `OrderStatusHistory` y cualquier validación fallida evita también la liberación.
- El perfil Repartidor sólo puede ejecutar `En reparto → Entregado` cuando el pedido está asignado a su propia cuenta. No puede iniciar reparto ni reiniciar ciclos; Administrador/Telefonista controlan las etapas anteriores. `/app/pedidos/<id>/` procesa acciones de estado por AJAX, actualiza insignia, siguiente acción e historial sin recarga ni pérdida de scroll.
- `/app/caja/terminales/` sustituye el cuaderno de Clover/Mercado Pago. Crea un corte diario por proveedor y autoguarda movimientos con total, propina, consumo derivado, nombre visible, ticket opcional y beneficiario explícito. Los cortes pueden cerrarse/reabrirse con auditoría.
- La conciliación física no duplica ventas ni propinas. Muestra cada proveedor por separado y compara la suma Clover + Mercado Pago contra mesas y pedidos registrados como Terminal, ya que el cobro original aún no identifica proveedor. También compara propinas por mesero/repartidor y resalta diferencias.
- Un pedido o mesa sólo puede vincularse a un movimiento de terminal. Al seleccionarlo se copian automáticamente su total y propina, pero ambos importes siguen editables para reflejar la terminal física; el vínculo desaparece de las demás filas. El autoguardado anuncia inmediatamente su estado y el script está encapsulado para evitar colisiones globales.
- La exclusividad del vínculo es global entre proveedores: usar un ticket en Clover lo retira de Mercado Pago y viceversa. Vincular una operación con propina puede guardarse inicialmente sin beneficiario para no trabar la captura; seleccionar después al mesero/repartidor actualiza la misma fila.
- Conciliación agrega `Transferencias` como tercer apartado. Clover/Mercado Pago vinculan únicamente entregas a domicilio y mesas pagadas con Terminal; Transferencias vincula exclusivamente entregas a domicilio pagadas por Transferencia. Los pedidos para Recoger nunca aparecen como candidatos. La comparación contable separa Clover+Mercado Pago contra Terminal y Transferencias contra Transferencia.
- Al vincular una entrega o mesa, la conciliación autocompleta total, propina y beneficiario: prioriza el destinatario de propina ya registrado y, si falta, usa el repartidor o mesero responsable. Los tres valores continúan editables después del vínculo.
- La cuarta pestaña `Conciliación` es de sólo consulta y resume la propina ganada por persona en Clover, Mercado Pago y Transferencias, además del total individual y general. El selector de vínculos sólo retira opciones después de una confirmación exitosa del servidor, evitando bloqueos visuales ante errores o respuestas simultáneas.
- El filtro redundante `Medio conciliado` fue eliminado: Clover, Mercado Pago, Transferencias y Conciliación se cambian exclusivamente mediante sus pestañas. Fecha y Persona conservan el apartado activo al enviarse.
- `/app/caja/adeudos/` administra cuentas por cobrar sin mezclar el estado financiero con el operativo. Cada pedido finalizado puede originar un solo `CustomerDebt` ligado a la agenda, con importe original, abonado, saldo y estados Pendiente/Parcial/Pagado/Condonado; `CustomerDebtMovement` audita abonos, condonaciones y reaperturas.
- La conciliación de Caja calcula el cobro esperado por fecha y medio con todas las operaciones realmente finalizadas: mesas cerradas, pedidos recogidos o entregados y abonos de adeudos registrados ese día. Excluye pedidos activos, cancelados y tickets trasladados a adeudo para no reconocer ingresos inexistentes ni duplicarlos; las restricciones de la lista `Vincular` permanecen independientes de este total contable.
- Administración también puede marcar directamente `No pagó` desde un pedido finalizado o `En reparto` en `/app/pedidos/` y `/app/caja/cambios/`. Cambios conserva por defecto las entregas en efectivo con cambio, pero filtra modalidad, estado y Efectivo/Terminal/Transferencia. Si se reporta desde `En reparto`, la operación primero registra el paso a `Entregado` y después crea el adeudo.
- En `/app/caja/cambios/`, tanto el folio como el nombre del cliente enlazan al editor del pedido para rastrear inmediatamente su ticket, historial y datos.
- En `/app/pedidos/clientes/`, sólo Administrador puede eliminar fichas. La eliminación conserva pedidos históricos, borra los domicilios de la ficha y queda bloqueada permanentemente si existe cualquier registro de adeudo; Telefonista no recibe el control y la URL también exige rol Administrador.
- El selector integrado de agenda también funciona en pedidos para Recoger. En esa modalidad muestra cada coincidencia una sola vez, completa exclusivamente nombre/teléfono y vincula la ficha al pedido sin copiar ni asociar domicilio.
- `/app/pedidos/` consulta automáticamente la URL y los filtros actuales cada siete segundos. Reemplaza sólo el listado cuando detecta cambios, conserva el scroll y pospone el ciclo mientras se ejecuta una transición o el operador interactúa con una fila.
- Administrador registra pedidos no pagados desde Caja o Adeudos, captura abonos y cambia cierres financieros. Telefonista accede al mismo tablero en sólo lectura. La ficha y el selector de clientes advierten el saldo abierto y enlazan directamente al historial correspondiente.
- Desde `En reparto`, el pedido queda en modo de sólo lectura para todos salvo Administrador: no se admiten productos, notas, cliente, domicilio, pago, propina, extras ni reasignación. Telefonista conserva exclusivamente `En reparto → Entregado`; sólo Administrador puede usar `Iniciar nuevo ciclo` tras un estado final.
- Excepción de propina: el Repartidor asignado puede capturar o corregirla mientras el pedido permanezca `En reparto`; al pasar a `Entregado` pierde ese permiso. En el capturador de Telefonista, Terminal ya no muestra montos de propina porque todavía no se conoce; Transferencia conserva su captura anticipada.
- La primera etapa de impresión añade dos vistas manuales de 80 mm para Mesero, Telefonista y Administrador, disponibles tanto en Mesas como en Pedidos. `Imprimir cocina` permite seleccionar partidas y cantidades parciales antes de abrir la vista previa; `Imprimir cobro` siempre contiene el ticket completo.
- Las vistas previas usan el diálogo normal del navegador/Windows y nunca imprimen al abrirse. Cocina prioriza cantidad, producto, complementos, modificaciones y comentarios; Cobro prioriza cliente, dirección/modalidad, pago, precios y total. La conexión USB directa con la OFICHIDO POS-8360 queda para una etapa posterior.
- El diseño térmico sigue las muestras `Tickets prueba.pdf`: encabezado compacto con negocio/folio/modalidad; Cocina muestra producto y comentario entre paréntesis con tipografía grande, datos operativos arriba y precios secundarios; Cobro muestra cliente/dirección primero, partidas compactas, total y método de pago. Los separadores y recuadros evitan bordes continuos y franjas negras. El ticket de cobro de mesa muestra `MESA: número` con peso normal.
- En Cocina, los separadores de partidas son guiones horizontales rectos, mientras nota general y producto comentado usan marcos de pequeños trazos diagonales para no confundirse, sin agregar una etiqueta textual al marco. Los tickets de cobro de Recoger/Domicilio imprimen nota general y el texto limpio de cada comentario por producto en jerarquía secundaria; Cobro de Mesas conserva su diseño sin esas adiciones.
- Los accesos separan intención: `Imprimir cocina` abre directamente la vista previa completa; `Imprimir cocina modificado` abre el selector de partidas y cantidades; `Imprimir cobro` continúa completo. Los tres accesos existen en Mesas, captura interna y detalle del Pedido.
- El ticket lateral de Pedidos reutiliza la proporción, estructura de partidas y crecimiento responsivo del ticket de Mesas. En escritorio ocupa una columna fluida y, cuando supera la altura visible, se desplaza la tarjeta completa para mantener accesibles productos, total, impresión y cierre; en pantallas estrechas vuelve al flujo vertical sin altura forzada.
- `Product.packaging_kind` distingue paquete, recipiente individual y `Cliente trae recipientes`; todos se agregan como partidas normales con cantidad, precio configurable, impresión y trazabilidad. Pedidos conserva una barra rápida; Mesas los presenta en la categoría normal `Envases`. Además, los formularios manuales de Corrida/Ejecutiva de ambos módulos incluyen selectores `− cantidad +` y guardan comida+cargos en una sola transacción. La clasificación los excluye siempre del menú público.
- Los formularios manuales de Corrida/Ejecutiva en Mesas usan las mismas tarjetas con fotografía y tres columnas visuales de Pedidos. Mantienen las reglas propias de Mesa: cada tiempo puede quedar pendiente, refill aparece junto a agua y Pierna/Muslo sólo se revela al seleccionar el pollo configurado.
- El editor de productos muestra explícitamente `Uso como envase`. Un POST inválido conserva los datos, muestra una alerta roja superior con todos los motivos enlazados a sus campos y enmarca cada control incorrecto; crear/editar también emite un mensaje de error general.
- La portada `/app/` usa una identidad visual renovada: marca compacta, tipografía Poppins con alternativas locales, encabezado verde en degradado y una cuadrícula responsiva sin numeración donde toda la tarjeta abre el módulo. La navegación superior omite `Ir a` y centra sus accesos en escritorio. El PIN rápido queda reservado estrictamente para Mesero: Administrador y superusuarios no ven sus controles ni pueden usar sus URLs, aunque acumulen el rol Mesero.
- `/app/caja/` conserva su comportamiento y AJAX, pero presenta una cabecera con regreso independiente, barra responsiva de herramientas, filtros compactos, contadores tipo insignia y estados vacíos discretos. Las filas operativas separan visualmente asignación y cobro y usan zonas táctiles más cómodas para repartidor y método de pago.
- Las pantallas internas mejoran progresivamente los `<select>` simples mediante `custom-select.js`: el control nativo continúa enviando valores y eventos, mientras la interfaz presenta disparador redondeado, flecha propia y menú web accesible. Los selectores múltiples y cualquier control marcado `data-native-select` conservan su implementación especializada.
- Adeudos, Corte de terminales, Cambios pendientes y Reporte de propinas comparten acabados de formulario con Caja: campos de texto/fecha redondeados, foco visible, tarjetas de filtros consistentes y `page-heading-actions` responsivo con separación uniforme entre accesos.
- El mapa de Mesas usa orden natural: Mesa 1–5 en la primera fila y Mesa 6–9 en la segunda, persistido por la migración `tables.0016`. Sus tarjetas conservan apertura/asignación, pero distinguen Disponible/Ocupada mediante acento superior, color, indicador y superficies táctiles modernas; en tablet y móvil abandonan coordenadas fijas para fluir en 3, 2 o 1 columnas.
- La cuenta abierta de Mesa usa una cabecera operativa compacta y reúne buscador + accesos Corrida/Ejecutiva en una barra responsiva. El cliente opcional se guarda por AJAX 650 ms después de escribir o al salir del campo, actualiza el encabezado y muestra Guardando/Guardado/Error; el backend normaliza el texto y evita actividades duplicadas cuando no cambió.
- En el detalle de mesa, la franja operativa prioriza a la izquierda búsqueda y creación de paquetes y conserva a la derecha un resumen compacto de mesa/cliente/modo; el nombre se autoguarda sin leyenda persistente. Las categorías navegan mediante un carrusel paginado con flechas, puntos y arrastre: todas permanecen visibles durante el recorrido y, al soltar, encaja en la página completa con mayor presencia.
- En los formularios visuales de comida corrida y ejecutiva para Mesas, la cabecera es compacta, no muestra la ayuda sobre tiempos pendientes, el agua del día se selecciona mediante una tarjeta con imagen y los envases aparecen al final justo antes de agregar al ticket.
- En esos formularios de Mesas, Primer y Segundo tiempo ocupan columnas compactas; el Tercer tiempo usa una columna derecha más amplia que abarca dos filas, mientras Agua y Refill aprovechan la segunda fila bajo los dos primeros tiempos para eliminar el espacio vacío.
- La captura interna de Pedidos tiene cabecera y comandos compactos, buscador y creación de paquetes en una sola franja, Envases como controles rápidos compactos solo en modo comida, categorías sin scrollbar y acciones de impresión ocultas mientras el ticket esté vacío.
- El control de inventario incluye una bitácora operativa en `/app/menu/inventario/historial/`. Permite filtrar por periodo, producto/nota/usuario, menú diario o fijo, grupo Mesas/Pedidos y motivo; resume entradas y salidas, conserva la autoría y pagina 30 movimientos por pantalla.
- `/app/reportes/` consolida únicamente mesas cerradas y pedidos recogidos/entregados. Cuenta Corrida, Ejecutiva, productos por orden, cada componente por tiempo y popularidad; además reconcilia inventario diario como inicial + aumentos = preparado, vendido finalizado, comprometido activo, ajustes a la baja y sobrante real.
- `/app/reportes/` es un reporte real de ventas finalizadas para Administración. Filtra por periodo y origen (Mesas, Pedidos, Recoger o Domicilio), excluye cuentas activas, borradores y cancelados, cuenta Corrida/Ejecutiva, desglosa cada primer/segundo/tercer tiempo, separa productos por orden y muestra los productos más servidos combinando ambos usos.
- Las existencias del menú diario se editan como tarjetas de dos columnas: Mesas y Pedidos muestran por separado disponible, umbral y cantidad comprometida. Cada tarjeta clasifica visualmente su estado como Disponible, Stock bajo o Agotado y fluye a una columna en pantallas pequeñas.
- Las existencias del menú diario usan 15 como umbral inicial de alerta, editable por producto y por grupo tanto al crear/editar el menú como desde Control de inventario. Sus notificaciones indican explícitamente `para Mesas` o `para Pedidos`; las alertas opcionales del menú fijo permanecen generales porque comparten existencia.
- Las existencias del menú diario usan un umbral de alerta predeterminado de 15, editable por producto e independientemente para Mesas y Pedidos tanto al crear el menú como al hacer un recuento. Sus notificaciones nombran el servicio afectado; las del menú fijo sólo indican producto y cantidad porque comparten existencia.
