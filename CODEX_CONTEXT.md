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

## Actualización: control de Administrador en Repartos (2026-09-18)

- En `/app/repartos/`, sólo Administrador puede corregir la propina de un pedido en cualquier momento. El Repartidor asignado conserva su autocaptura única existente (una sola vez, en Efectivo/Terminal, mientras esté `En reparto`). Telefonista pierde la edición de propina en esta pantalla, aunque conservaba acceso de lectura/asignación limitada previa.
- La captura interna de pedidos (Telefonista/Administrador en `/app/pedidos/<id>/editar/`) conserva intacta su propia captura de propina para Transferencia, ahora mediante un endpoint separado `orders:internal_order_tip_update`. `deliveries:delivery_tip_update` queda reservado a Repartos (Administrador/Repartidor) y a Caja (sólo Administrador).
- Se agregó un control de método de pago (Efectivo/Terminal/Transferencia) visible únicamente para Administrador en cada tarjeta de `/app/repartos/`, reutilizando el mismo servicio de Caja (`cashier:payment_update`/`update_cashier_payment`). Antes, el método de pago sólo se mostraba de solo lectura en esta pantalla. Al guardar, la tarjeta recarga para reflejar de forma consistente cambio, propina y demás datos derivados del pago.
- La asignación de repartidor en Repartos ya era exclusiva de Administrador (decorador `@role_required(ADMIN)` en `delivery_assign`); no se modificó.
- No se requirió migración. Se ejecutó la suite de `orders` (33 pruebas) sin fallos; no se agregaron pruebas nuevas, siguiendo el patrón habitual del proyecto de validación manual por bloque.

## Corrección: billetes de efectivo en el control de pago de /app/repartos/ (2026-09-18)

- Un primer intento agregó la expansión de billetes de efectivo en `/app/pedidos/`; el desarrollador aclaró que el pedido original era para el control de método de pago recién agregado en `/app/repartos/`. Ese cambio en `order_board_item.html`/`order-list.js` fue revertido por completo (`git checkout`) y no queda rastro en el código.
- El control de método de pago exclusivo de Administrador en `/app/repartos/` (ver sección "control de Administrador en Repartos") sólo cambiaba Efectivo/Terminal/Transferencia sin permitir elegir con qué billete pagó el cliente.
- Al elegir Efectivo, la tarjeta ahora despliega los mismos montos que Caja ($20/$50/$100/$200/$500/Exacto) más un campo de monto libre con autoguardado (debounce 600 ms). Cada botón sigue siendo un `<form>` independiente que reutiliza el mismo endpoint `cashier:payment_update`, y guarda recargando la tarjeta para reflejar cambio/"Monto por definir" de forma consistente.
- `delivery_board` agrega `cash_denominations` ([20, 50, 100, 200, 500]) al contexto; no se tocó `update_cashier_payment` ni ningún otro backend.
- No se requirió migración. Se ejecutó la suite de `orders` (33 pruebas) sin fallos.

## Corrección: ticket de Mesas/Pedidos ilegible en tablets (Galaxy Tab A9+) (2026-09-18)

- Diagnóstico verificado visualmente con Playwright headless (login temporal `qa_visual_temp`, luego eliminado) en `/app/mesas/cuentas/<id>/` y `/app/pedidos/<id>/editar/` a 1280×800 (Tab A9+ horizontal, viewport CSS real del dispositivo, no 1340×800 como se asumía) y 800×1280 (vertical). Intentos previos de otras IAs habían fallado porque `static/css/app.css` (~11 000 líneas) acumula muchas reglas `!important` duplicadas para los mismos selectores del ticket (`.table-pos-layout .table-ticket`, `.internal-live-ticket`, `.quantity-buttons`); la última declaración de cada selector en el archivo es la que realmente gana, sin importar cuántas versiones "para iPad Air" existan antes.
- **Causa 1 (botones de partida "separados"):** `.ticket-item-note-button` (botón "Nota") y `.ticket-edit-extras` ("Editar extras") usaban `margin-left: auto` dentro de `.quantity-buttons` (`display: flex`, sin `flex-wrap`). Esto los empuja al extremo derecho de la fila, dejando un hueco enorme frente a `−/+/×` en columnas angostas (el ticket de Mesas/Pedidos es una barra lateral de ~340-740px en tablet, no todo el ancho de escritorio). Ocurría en cualquier ancho, pero era más notorio en tablet. Corregido quitando `margin-left: auto` de ambos botones y agregando `flex-wrap: wrap` a `.quantity-buttons`; ahora quedan agrupados junto a `−/+/×` (o bajan a su propia fila completa si no caben, reactivando sin cambios adicionales las reglas `width:100%` para iPad Air de 1000-1200px que antes eran inertes por el `display:flex` sin wrap).
- **Causa 2 (ticket "no se expande", no se ve lo agregado):** en horizontal con poca altura (Tab A9+: 800px de alto), la lista de partidas es lo único con scroll; los elementos fijos (método de pago, "Agregar nota general", 3 botones de impresión, "Guardar sin cerrar"/"Cerrar captura", "Cobrar y cerrar cuenta") ya consumían la mayor parte del `max-height` del ticket, dejando ~140-170px visibles (1-2 partidas) de un ticket con 6-9 artículos. Los medios "iPad Air horizontal" existentes estaban acotados a `max-width: 1200px`, por lo que Tab A9+ (1280px de ancho en horizontal) no recibía ningún ajuste específico.
- Corrección: nuevo bloque al final de `app.css`, con `@media (pointer: coarse) and (orientation: landscape) and (max-height: 900px)` — se basa en la **altura** disponible, no en un ancho de dispositivo puntual, para cubrir Tab A9+, iPad Air y cualquier tablet corta futura sin repetir el patrón de parches por pixel exacto. Compacta impresión (3 columnas en una fila, como ya existía para celular), "Guardar/Cerrar" (2 columnas), método de pago, "Agregar nota general", total y "Cobrar y cerrar cuenta". No toca la altura ni posición del panel del ticket (evita que se desborde de la pantalla).
- Verificado con capturas: en Mesas horizontal Tab A9+ las partidas visibles subieron de ~1.7 a ~2.8; en Pedidos horizontal Tab A9+ de ~2 a ~4.7. Verificado también en iPad Air horizontal (1180×820) sin regresión: mismo diseño compacto, sin overlaps.
- No se requirió migración ni cambio de Python. No se agregaron pruebas automáticas (cambio puramente visual/CSS); se ejecutó la suite completa (70 pruebas) sin fallos tras el cambio.
- Nota para el futuro: `app.css` tiene numerosas reglas duplicadas con comentarios "Prioridad final"/"para que ninguna regla histórica del iPad vuelva a anularla" que en realidad SÍ vuelven a anularse entre sí por orden de aparición en el archivo. Antes de tocar el ticket de Mesas/Pedidos, verificar cuál es la ÚLTIMA declaración de cada selector en el archivo (no confiar en el comentario ni en la posición aparente), idealmente reproduciendo visualmente con un navegador headless en las dimensiones CSS reales del dispositivo reportado (no asumir resolución física/DPI).

## Corrección: guisado de pollo sin raciones al agregarlo por "Comida por orden" en Pedidos (2026-09-18)

- Reportado por el desarrollador: en `/app/pedidos/<id>/editar/`, agregar el guisado de pollo del día desde "Comida por orden" rechazaba el producto con `"<producto> no tiene raciones configuradas para pedidos"`, aunque el mismo producto sí se podía agregar sin problema desde Mesas.
- Causa raíz confirmada (no era un problema de datos): la existencia diaria del guisado de pollo se controla por pieza (`chicken_piece`: pierna/muslo) y sólo existen filas de `DailyProductStock` para `leg`/`thigh`, nunca para pieza vacía. En Mesas, `tables/templates/tables/_catalog_product_card.html` ya detecta `product.id == daily_menu.chicken_stew_id` y agrega `data-chicken-choice` + un input oculto `chicken_piece`, abriendo el diálogo Pierna/Muslo antes de enviar. La tarjeta equivalente de Pedidos (`orders/templates/orders/_internal_product_card.html`, compartida por el catálogo general y por "Comida por orden") nunca tuvo esa lógica: enviaba siempre `chicken_piece=""`, y además la vista `internal_order_daily_product_add` ni siquiera leía `chicken_piece` del POST para reenviarlo al servicio. Resultado: la reserva de stock buscaba una fila con pieza vacía que nunca existe y rechazaba el producto.
- Corrección, replicando exactamente el patrón ya probado de Mesas: `_internal_product_card.html` agrega `data-internal-chicken-choice` + `<input type="hidden" name="chicken_piece">` en ambos formularios (agregar rápido y Personalizar) cuando `daily_order` y el producto es `daily_menu.chicken_stew_id`; `internal-order-form.js` intercepta el envío de `[data-internal-add]` con ese atributo para abrir el diálogo `[data-internal-chicken-dialog]` ya existente (reutilizado, antes sólo servía a Corrida/Ejecutiva) antes de enviar; la vista `internal_order_daily_product_add` ahora reenvía `chicken_piece=request.POST.get("chicken_piece", "")` a `add_internal_order_product`.
- Verificado en `shell` reproduciendo el error exacto con datos reales de hoy (`Pollo a la crema`, sin pieza) y confirmando éxito con `chicken_piece="leg"`; también se verificó que el HTML servido para "Comida por orden" ya incluye el atributo y el input ocultos en ambos formularios. No se requirió migración. Se ejecutó la suite completa (70 pruebas) sin fallos.
- El mismo patrón (tarjeta genérica de catálogo reutilizada por "Comida por orden" sin heredar lógica especial del guisado de pollo) es la sospecha principal si aparece un bug similar en el futuro con otro componente que dependa de una elección adicional antes de reservar stock.

## Corrección: /app/caja/terminales/ dejaba de crear la siguiente tarjeta vacía (2026-09-18)

- Reportado por el desarrollador: al capturar cobros de Terminal en `/app/caja/terminales/`, la primera tarjeta guardada correctamente abría una segunda tarjeta vacía, pero al llenar esa segunda ya no aparecía una tercera; había que refrescar la página para poder seguir capturando. Reproducido con Playwright headless contra el servidor local (no era específico de celular; el mismo bug ocurre en cualquier tamaño de pantalla).
- Causa raíz en `static/js/cashier-terminal-board.js`: `saveRow()` marca `row.dataset.saving = "1"` antes del `fetch` y sólo lo regresa a `"0"` dentro de su bloque `finally`. `appendBlankFrom(row)` (que crea la siguiente tarjeta vacía) se invoca **dentro** del `try`, es decir, todavía con `data-saving="1"` puesto en la fila que se está guardando. Como esa función clona la fila con `row.cloneNode(true)`, la tarjeta nueva nace con `data-saving="1"` copiado. Ese valor nunca se reinicia para el clon (el `finally` que lo limpia pertenece a la fila original, no al clon), así que la primera vez que se intenta guardar la tarjeta nueva, `saveRow` entra de inmediato a `if (row.dataset.saving === "1") { ...; return; }` y se queda atorada en "Pendiente de guardar…" para siempre. Un refresco de página vuelve a renderizar la fila desde el servidor sin ese atributo, por lo que "funciona una vez" después de cada recarga y se vuelve a atorar en el siguiente clon.
- Corrección: `appendBlankFrom` ahora también hace `delete clone.dataset.saving; delete clone.dataset.pendingSave;` junto con los demás reinicios (`movementId`, `savedTotal`, `savedTip`) para que la tarjeta nueva nazca realmente limpia.
- Verificado con Playwright guardando 5 tarjetas consecutivas sin recargar la página; cada una dejó una tarjeta vacía lista inmediatamente después de guardarse. No se requirió migración ni cambio de backend. Se ejecutó la suite completa (70 pruebas) sin fallos.
- Nota para el futuro: cualquier otro flujo que use `cloneNode(true)` para generar una fila/tarjeta "en blanco" a partir de una fila existente debe reiniciar explícitamente los atributos de estado transitorio (`data-saving`, `data-pending-save` y similares), no sólo los campos de datos visibles; `cloneNode` copia el DOM tal cual esté en ese instante, incluidos atributos internos de control.

## Corrección: productos sueltos de "Comida por orden" ausentes en Mesas (2026-09-18)

- Reportado por el desarrollador: en `/app/mesas/cuentas/<id>/`, la pestaña "Comida por orden" no mostraba bolillo, tortilla, consomé preparado, etc., aunque sí aparecían en Pedidos; pidió que la disponibilidad de Mesas fuera igual a la que ya existe en Pedidos.
- Causa raíz: existe una categoría real llamada "Comida por orden" (id 8, `show_on_table_lunch=True`) con productos individuales sueltos (hoy: Frijol negro de la olla, Bolillo, Tortilla media docena) distintos de los 8 componentes fijos 2+2+3 del `DailyMenu`. `orders/views.py` (Pedidos) ya calculaba `daily_order_loose_products` filtrando esa categoría por stock del canal `ORDERS` y los sumaba a la sección virtual. `tables/views.py` (Mesas) excluye explícitamente esa categoría del catálogo normal (`.exclude(Q(name__iexact="Comida por orden"))`) pero nunca tuvo el equivalente `daily_order_loose_products`: sus productos sueltos jamás se consultaban, sin importar el stock configurado.
- Corrección: se agregó en `tables/views.py` el mismo cálculo de `daily_order_loose_products` que Pedidos, usando `channel=DailyProductStock.Channel.TABLE`, excluyendo los productos ya cubiertos por `daily_order_products` para no duplicarlos. Se sumó a `selector_products`/`has_customization` (para personalización y buscador) y se agregó al contexto. `tables/templates/tables/table_detail.html` ahora itera también `daily_order_loose_products` en la sección "Comida por orden", sin pasar `daily_order=True` (igual que Pedidos), por lo que usan el endpoint normal `table_item_add` en vez del especial de menú diario.
- Verificado con Playwright: las tres tarjetas (Frijol negro de la olla, Bolillo, Tortilla media docena) ahora aparecen con foto/precio/controles en Mesas, y se confirmó que agregar Bolillo al ticket de una cuenta real funciona correctamente (después se eliminó el registro de prueba).
- Nota de datos: Bolillo y Tortilla media docena no tienen ninguna fila de `DailyProductStock` (ni tabla ni pedidos), por lo que `filter_products_by_stock` los trata como "no rastreados" y siempre los muestra sin importar el canal; Frijol negro de la olla sí tiene stock diario configurado para ambos canales (20 c/u hoy). Si en el futuro se agrega "Consomé preparado" u otro producto a esta categoría y no aparece, primero revisar si tiene stock configurado para el canal correspondiente (Mesas usa `channel=table`, Pedidos usa `channel=orders`) antes de sospechar de este código.
- No se requirió migración. Se ejecutó la suite completa (70 pruebas) sin fallos.

## Corrección: menú de "Huevo opcional" no se despliega en celular (Corrida/Ejecutiva) (2026-09-18)

- Reportado por el desarrollador: en el constructor visual de Comida corrida/Comida ejecutiva (Mesas y Pedidos comparten el mismo `.visual-package-dialog`), el desplegable "Huevo opcional" no abre sus opciones en varios celulares distintos. Confirmado en varios teléfonos, no reportado en tablet/escritorio.
- A partir de aquí el diagnóstico se hizo leyendo código y CSS (no con navegador automatizado, por preferencia del desarrollador de probar manualmente).
- Causa raíz: `static/css/app.css:1603` aplica `overflow-y: auto` al `<form>` del paquete (`form[data-internal-package]`/`form[data-package-form]`) dentro de `@media (max-width: 900px)`, para que su contenido se desplace dentro del diálogo en pantallas de celular. Una corrección posterior ("Prioridad definitiva: huevo visible…", ya existente) le puso `overflow: visible !important` a `.package-egg-choice` y sus envoltorios internos para que el menú del `<select>` mejorado (`custom-select.js`) no quedara recortado, pero nunca tocó el propio `<form>`. Como el recorte real ocurre en el ancestro con `overflow-y:auto` (el formulario), no en sus hijos, el menú seguía invisible en celular sin importar cuántos hijos tuvieran `overflow:visible`.
- Se descartó "arreglar" quitando o forzando `overflow:visible` en el formulario mientras el menú está abierto: ese formulario ya tiene una posición de scroll aplicada (`overflow-y:auto`), y cambiarla a `visible` habría hecho que el contenido "saltara" a su posición sin desplazamiento en cuanto se abriera el huevo, y regresara al cerrarlo.
- Corrección real: `static/js/custom-select.js` ahora detecta cuando el `<select>` mejorado vive dentro de `.package-egg-choice` y, sólo en ese caso, calcula la posición real del disparador (`getBoundingClientRect`) y coloca su menú como `position: fixed` (clase `.is-escaped` + variables CSS `--escaped-menu-top/left/width/max-height`), decidiendo automáticamente si abre hacia arriba o hacia abajo según el espacio disponible. `position: fixed` no depende de ningún contenedor con scroll, así que el menú ya no queda recortado sin tocar el `overflow-y:auto` del formulario ni su posición de scroll. El resto de los `<select>` del sitio (todos los demás usos de `custom-select.js`) no se ven afectados: sólo se activa dentro de `.package-egg-choice`.
- Este menú lo comparten Mesas y Pedidos porque ambos reutilizan `.visual-package-dialog`/`form[data-internal-package]`/`form[data-package-form]`.
- **Corrección (primer intento, insuficiente):** el diagnóstico inicial (posicionar el menú del huevo como `position:fixed` para escapar de un `overflow-y:auto` en el formulario) era real pero incompleto: el desarrollador probó en celular real y seguía fallando. El verdadero bloqueador era otro: el toque nunca llegaba al control porque `.package-egg-choice` terminaba **visualmente encimado** sobre la sección "Tercer tiempo".
- **Causa raíz verificada** (con navegador automatizado, esta vez sí, porque las correcciones a ciegas habían fallado dos veces): en `@media (max-width: 900px)`, `.table-package-visual-extras` (contenedor de agua/refill/bolillo/huevo/comentario) tenía `display: contents`, lo que hace que sus hijos se conviertan en elementos directos de la cuadrícula EXTERNA de los tres tiempos (`.package-visual-groups`). Como "Tercer tiempo" ocupa explícitamente `grid-row:2` a ancho completo, y el huevo (`.package-egg-choice`, inyectado por `package-egg.js`) no tenía una posición propia definida para esa combinación de ancho/tipo de paquete, terminaba renderizado exactamente sobre esa sección. El toque real llegaba al `<h3>`/tarjetas de "Tercer tiempo", no al `<select>` — confirmado con `document.elementFromPoint()` en las coordenadas reales del control, antes de cualquier corrección visual.
- `app.css` tiene docenas de reglas duplicadas para este mismo contenedor en distintos anchos y tipos de paquete (`data-package-kind="running"` vs `"executive"`), cada una con distinta especificidad; "la última regla gana" no basta si una regla anterior tiane más clases/atributos que la nueva. Hubo que igualar la especificidad exacta de la regla que realmente ganaba (`form[data-package-form][data-package-kind="…"] .table-package-visual-extras > .package-egg-choice`) para poder finalmente vencerla.
- Corrección final: nuevo bloque al final de `app.css`, dentro de `@media (max-width: 900px)`, que fuerza `.table-package-visual-extras` a `display:grid` (nunca `contents`) con una sola columna a ancho completo (`grid-column:1/-1`), y coloca cada hijo (agua, refill/bolillo, huevo, comentario) en `grid-column:1; grid-row:auto` — repetido tanto para el selector genérico como para las variantes calificadas `[data-package-kind="running"]` y `[data-package-kind="executive"]`, para garantizar que gane sin importar el tipo de paquete.
- Verificado con navegador automatizado (a petición explícita del desarrollador para este caso, tras dos correcciones fallidas): clic real (no evento sintético) sobre las coordenadas del control en los 4 contextos —Mesas Corrida, Mesas Ejecutiva, Pedidos Corrida, Pedidos Ejecutiva— a 390×844 (tamaño celular), confirmando que el menú se abre y muestra "Sin huevo", "Huevo estrellado" y "Huevo revuelto". También se confirmó sin regresión en iPad Air horizontal (1180×820) y escritorio (1440×900).
- No se requirió migración ni cambio de Python. Se ejecutó `python manage.py check` y la suite completa (70 pruebas) sin fallos.
- Nota para el futuro: en este archivo, cuando una regla usa `!important` pero pierde contra otra también con `!important`, sospechar primero de una diferencia de **especificidad** (conteo de clases/atributos/elementos), no sólo de orden de aparición; el orden sólo decide empates de especificidad. Verificar con `document.styleSheets`/`getComputedStyle` en el navegador cuál regla gana realmente antes de agregar una más.

## Actualización: estación de impresión con latido y expiración de trabajos (2026-09-18)

- Problema reportado: la Dell requería activar manualmente PowerShell/venv/`python agent.py` cada vez (ya resuelto en parte por el desarrollador con una Tarea Programada de Windows que arranca `agent.py` solo al iniciar sesión). Además, cuando el agente estaba apagado, cualquier intento de imprimir seguía creando `PrintJob` en cola; al reconectarse horas después, esos tickets viejos salían todos de golpe, sin que ya tuvieran sentido.
- Arquitectura previa (confirmada leyendo el código, no solo la descripción): `print_station` sólo tenía el modelo `PrintJob` (`pending/printing/printed/failed`) y vistas para encolar (`request_print`→`queue_ticket`), reclamar (`claim_job`) y finalizar (`finish_job`) trabajos. No existía ningún concepto de "estado de la estación" ni de vigencia: `queue_ticket` creaba el `PrintJob` sin verificar si algún agente estaba realmente escuchando, sólo comprobaba que `PRINT_AGENT_TOKEN` estuviera configurado.
- Se agregó el modelo `PrintStation` (fila única `name="cocina"`, ya que sólo hay una Dell/una POS-80): guarda `printer_available`, `last_heartbeat_at` y `last_error`. Su propiedad `is_online` exige latido de menos de `HEARTBEAT_TIMEOUT_SECONDS=25` segundos **y** `printer_available=True`.
- Nuevo endpoint `POST /app/impresion/agente/latido/` (`print_station:heartbeat`), autenticado igual que `claim_job`/`finish_job` (Bearer token). El agente lo llama cada 10 s reportando si Windows ve la POS-80 conectada.
- `queue_ticket()` ahora exige `PrintStation.current().is_online` antes de crear cualquier `PrintJob`; si no, levanta `ValueError` con un mensaje claro y **no se inserta nada**. Los tres llamadores existentes (`request_print`, y las vistas de "imprimir cocina modificado" en `orders`/`tables`) ya capturaban `ValueError` para otros casos, así que el nuevo rechazo se integró sin tocar esas vistas; sólo `request_print` no capturaba el error todavía y se corrigió para devolver `503` con el mensaje al JSON que ya consume `direct-print.js`.
- `PrintJob` ganó `expires_at` (calculado al crear: `created_at + 90 s`) y el estado `EXPIRED`. `claim_job` ahora expira en bloque cualquier `PENDING` vencido (o sin `expires_at`, para limpiar trabajos previos a este cambio) antes de tomar el siguiente trabajo válido — cubre la condición de carrera "se creó el ticket justo antes de que la impresora se desconectara".
- `direct-print.js` ya mostraba errores en un aviso rojo temporal (`notice(..., true)`) sólo cuando fallaba una impresión; con el nuevo `503` ese mismo mecanismo ya cubre el pedido de "sólo avisar cuando falla, no un indicador permanente". Se agregó además el caso `status === "expired"` al polling (`watchJob`) para no dejarlo sin explicación.
- `admin.py`: se registró `PrintStation` (para ver el latido sin tocar la base a mano) y se corrigió `retry_jobs` para renovar `expires_at` al reintentar manualmente un trabajo viejo desde el admin — si no, el reintento se auto-expiraría en el siguiente `claim_job`.
- `print_station/dell_agent/agent.py`: se agregó `printer_is_connected()` (lee el bit `PRINTER_STATUS_OFFLINE` de Windows, sin intentar imprimir para probar) y un hilo (`threading`) separado que manda el latido cada 10 s de forma independiente del bucle que reclama/imprime trabajos, para que nunca se atrase por estar ocupado. El bucle principal también revisa `printer_is_connected()` justo antes de imprimir, por si la impresora se desconectó en el margen entre latidos.
- `print_station/dell_agent/README.md` quedó actualizado con el flujo de operación diaria ("prender Dell → prender impresora → listo"), incluyendo los comandos exactos de la Tarea Programada que el desarrollador ya ejecutó, para poder repetirlos si se reinstala Windows o se cambia de equipo.
- Migración `print_station.0002_printstation_printjob_expires_at_and_more` pendiente de aplicar en el servidor (`python manage.py migrate`). Se agregaron 5 pruebas nuevas (estación fuera de línea rechaza sin crear job, latido vencido rechaza, heartbeat habilita impresión, expiración de trabajos viejos en `claim_job`) y se ajustó la prueba existente para partir de una estación en línea. Se ejecutó la suite completa (74 pruebas) sin fallos.
- Pendiente de que el desarrollador aplique en la Dell: reemplazar `agent.py` por la versión nueva y reiniciar la Tarea Programada (`Stop-ScheduledTask`/`Start-ScheduledTask "SuperCocina Print Agent"`, o simplemente reiniciar la Dell). El comportamiento del `agent.py` con latido en hilo aparte y detección de impresora **no se pudo probar contra hardware real** (no hay acceso a la Dell/POS-80 desde este entorno); sólo se validó sintaxis (`py_compile`) y la lógica del lado Django con pruebas automatizadas.
- Riesgo/limitación conocida no cubierta por este bloque: si el agente muere DESPUÉS de reclamar un trabajo (queda en `PRINTING`) pero antes de imprimir, ese trabajo no se reintenta automáticamente (evita duplicar en papel); requiere revisión manual en `/admin/print_station/printjob/` como ya indicaba el README. Es un caso distinto al que pidió resolver el desarrollador (trabajos que nunca debieron crearse) y queda fuera de alcance de este cambio.

## Actualización: cambio rápido de mesero sin PIN, contraseña una vez al día (2026-09-19)

- Pedido del desarrollador: quitar el PIN del cambio rápido de meseros en tablet compartida. La nueva regla: cada mesero inicia sesión con su contraseña real sólo una vez al día en cada tablet; después, cambiar entre meseros que ya hicieron ese inicio de sesión hoy usa el mismo botón/desplegable "Cambiar mesero" que ya existía, sin pedir nada más. Se pidió explícitamente borrar el código del PIN, no dejarlo en desuso.
- Se reemplazó el concepto de "tablet confiable por 12 h + PIN por mesero" (`accounts/quick_switch.py`: `TRUST_KEY`/`TRUST_HOURS`/`quick_switch_is_trusted`/`enable_quick_switch`) por uno de "quiénes ya iniciaron sesión con su contraseña HOY en esta tablet" (`DAILY_LOGINS_KEY`: diccionario `{user_id: "YYYY-MM-DD"}` en sesión, expuesto vía `logged_in_today_ids()`).
- Detalle importante descubierto al implementar: Django `login()` hace `request.session.flush()` (borra toda la sesión) cada vez que autentica a un usuario DISTINTO del que ya estaba en la sesión (protección contra fijación de sesión). Por eso `DAILY_LOGINS_KEY` debe leerse ANTES de llamar `login()` (`snapshot_daily_logins`) y volver a escribirse DESPUÉS (`restore_daily_logins`); si no, cada cambio de mesero borraría el registro de los meseros anteriores del día. Esto se centralizó en `accounts/views.py:_complete_quick_switch()`, usado tanto por `login_view` como por `quick_switch`.
- Otro hallazgo al escribir las pruebas: `login_view` redirige de inmediato a quien YA tiene sesión iniciada (`if request.user.is_authenticated: return redirect(...)`), así que un segundo mesero nunca podría llegar a la página de login normal mientras el primero sigue activo en la tablet. Por eso el registro de "primera vez hoy" del segundo mesero en adelante NO pasa por `/cuentas/login/`, sino por la misma pantalla/formulario de `accounts:quick_switch`: si el mesero elegido ya está en `logged_in_today_ids`, cambia al instante (sin campos); si no, ese mismo formulario pide su **contraseña real** (reemplaza al PIN 1 a 1) y, si es correcta, lo registra para el resto del día.
- `Profile` perdió `quick_pin_hash`, `pin_failed_attempts`, `pin_locked_until` y sus métodos (`has_quick_pin`, `pin_is_locked`, `set_quick_pin`, `check_quick_pin`); migración `accounts.0004_remove_profile_pin_failed_attempts_and_more`. Se borraron `QuickPinSetupForm`, la vista `quick_pin_setup`, su URL (`accounts:quick_pin_setup`, antes `/app/perfil/pin/`) y su plantilla `accounts/templates/accounts/quick_pin_setup.html`.
- `QuickSwitchForm` ahora sólo tiene `waiter_id` (oculto) y `password` (opcional a nivel de formulario; la vista decide si es obligatorio según si ese mesero ya está en `logged_in_today_ids`).
- El desplegable de `base_internal.html` (mismo bloque usado en Mesas y en el resto de `/app/`) y la pantalla completa `accounts/templates/accounts/quick_switch.html` (la que aparece sola cuando la tablet se bloquea por 3 min de inactividad) ahora muestran, por cada mesero: un botón directo si ya inició sesión hoy, o un campo de contraseña si es su primera vez. Se quitó el enlace "Configurar PIN/Habilitar tablet" por completo: ya no existe un paso de configuración previo, cualquier mesero activo puede recibir un cambio hacia él en cuanto escribe su contraseña una vez.
- `accounts/middleware.py` (`QuickSwitchLockMiddleware`) se simplificó: ya no "auto-habilita" nada (eso ahora ocurre explícitamente en las vistas de login/cambio); sólo conserva el bloqueo por inactividad para cualquier mesero (nunca Administrador).
- El bloqueo por inactividad (3 min, `static/js/quick-switch-idle.js`, sin cambios) y el botón "Bloquear tablet" siguen igual; sólo cambió qué pasa DESPUÉS de llegar a la pantalla de selección.
- Pruebas actualizadas/nuevas en `accounts/tests.py` (6 en total): administrador no ve el control ni puede usar la pantalla; login normal registra al mesero para hoy; primer cambio hacia otro mesero exige contraseña real (rechaza vacío e incorrecta, acepta la correcta y lo registra); un segundo cambio de vuelta al mismo mesero ya no pide nada; el bloqueo por inactividad sigue redirigiendo a la pantalla de cambio. Se ejecutó la suite completa (78 pruebas) sin fallos.
- Pendiente de verificación manual por el desarrollador en un dispositivo real (no se probó con Playwright para esta tarea, por preferencia general de pruebas manuales).

## Actualización: estación de impresión (latido) no funcionaba en producción — diagnóstico y arreglo (2026-09-19)

- Contexto: tras desplegar el bloque anterior (latido/expiración) a Lightsail, `/admin/print_station/` sólo mostraba "Print jobs", nunca "Print stations", pese a `git pull`+`migrate` aplicados y el servicio (`super-cocina.service`, Gunicorn en `127.0.0.1:8000` detrás de Nginx+Cloudflare en `supercocina.win`) reiniciado. Se descartó, en orden: mismatch de `DJANGO_SETTINGS_MODULE` (no hay settings separado de producción; ni el `.service` ni `.env` lo fijan, así que Gunicorn y `manage.py shell` usan el mismo `config.settings`), caché de Nginx (`nginx -T` sin ninguna directiva `proxy_cache`), y caché de Cloudflare/CDN (confirmado con `journalctl -u super-cocina -f`: una recarga real del navegador SÍ generó una línea `GET /admin/print_station/ ... 200` fresca en Gunicorn en el mismo instante).
- Diagnóstico definitivo: `python manage.py shell` con `django.test.Client` **debe fijar `SERVER_NAME` a un host permitido** (`c.get(url, SERVER_NAME='supercocina.win')`); sin eso, el `Client` manda `Host: testserver` y `ALLOWED_HOSTS` en producción lo rechaza con `400` — un `Client()` "a secas" en shell de producción da un 400 engañoso que parece "no se ve el modelo" pero en realidad nunca llegó a renderizar nada. Con `SERVER_NAME` correcto, el admin sí devuelve `200` con "Print stations" incluido: la app y el registro de `PrintStation` siempre estuvieron bien; lo que el desarrollador veía en su navegador era caché de su propio navegador/pestaña, no del servidor (confirmado: un refresco forzado posterior sí lo mostró).
- Causa real de la urgencia ("la impresora no prende"): `PrintStation.current().last_heartbeat_at` era `None` — el `agent.py` corriendo en la Dell (`C:\SuperCocina\print-agent\dell_agent`, **no es un repo git**, el código se copió a mano) seguía siendo la versión previa al latido de esta sesión. Se reemplazó `agent.py` completo por la versión con `heartbeat_loop()` (con respaldo `agent.py.bak.20260919` primero). Tras eso, ejecutándolo manualmente (`& .\.venv\Scripts\python.exe .\agent.py`) el latido sí llegó (`is_online: True`), pero la Tarea Programada `"SuperCocina Print Agent"` se quedaba en estado `Queued` para siempre sin lanzar ningún proceso.
- Causa de la Tarea Programada atorada: estaba configurada con `RunLevel: Highest` (ejecutar como administrador) + `LogonType: Interactive`; imprimir no requiere privilegios de administrador y ese requisito de elevación impedía que arrancara sola de forma confiable. `schtasks /Change /RL LIMITED` pide contraseña de Windows del usuario (que el dueño de la Dell no conoce) — se evitó por completo exportando la tarea (`Export-ScheduledTask`), reemplazando `HighestAvailable` por `LeastPrivilege` en el XML, y re-registrándola con `Register-ScheduledTask -Xml ... -Force` (no pide contraseña porque el `LogonType` sigue siendo `InteractiveToken`, sin credenciales almacenadas). Con eso, `Start-ScheduledTask` sí lanzó el proceso solo, y el latido llegó a Lightsail con la estación arrancada 100% por la Tarea Programada (sin ninguna ventana manual abierta): `printer_available: True`, `is_online: True`.
- Terminal usada en cada paso (importante para reproducir): comandos de Django/`manage.py shell`/`journalctl`/`nginx -T` siempre en la sesión **SSH de Lightsail** (usuario `ubuntu@ip-172-26-7-203`); comandos de PowerShell/`Get-ScheduledTask`/reemplazo de `agent.py` siempre **físicamente en la Dell** (`DESKTOP-3MHJVQM`, usuario `lleva`) — la sesión SSH hacia la Dell corre en `cmd.exe` por defecto (sin cmdlets de PowerShell; hay que escribir `powershell` primero si se usa esa vía), y las tareas con `LogonType: Interactive` no arrancan si no hay una sesión de escritorio real detrás, así que para diagnosticar el estado `Queued` fue necesario estar sentado frente al equipo.
- Pendiente de confirmar por el desarrollador: una impresión real de un ticket de cocina/cuenta de principio a fin contra la POS-80 física (hasta este punto sólo se confirmó el latido, no una impresión completa post-arreglo).
- Nota para el futuro: `C:\SuperCocina\print-agent\dell_agent` en la Dell NO es un clon de git; cualquier cambio futuro a `agent.py`/`README.md` debe copiarse a mano (no hay `git pull` posible ahí) — considerar convertirlo en un repo real si se vuelven frecuentes los cambios a este agente.
- Nota para el futuro (diagnóstico): al usar `django.test.Client` desde `manage.py shell` en un servidor de producción para simular una petición real (bypaseando Cloudflare/Nginx), siempre pasar `SERVER_NAME=<dominio permitido>`; de lo contrario `ALLOWED_HOSTS` lo rechaza con un `400` que puede confundirse con "la vista/el modelo no está" cuando en realidad la petición nunca se procesó.

## Actualización: Tarea Programada de la Dell se queda "atorada" y deja de lanzar el agente (2026-09-21)

- Dos días después del arreglo anterior, el desarrollador reportó que la app volvía a decir "impresora no disponible" tras apagar/prender la Dell con la impresora ya conectada. Diagnóstico: `Get-Process python` no mostraba ningún proceso pese a que la Tarea Programada ya debía haber arrancado sola al iniciar sesión.
- Para diagnosticar sin adivinar, se activó el historial detallado de Task Scheduler (viene desactivado por defecto en Windows): `wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true`, y luego se leyó con `Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" ...`. Esto reveló el evento id `322`: *"Task Scheduler did not launch task ... because instance ... of the same task is already running"* — Windows tenía registrada una instancia "fantasma" de una ejecución anterior que nunca se limpió correctamente (de pruebas manuales previas con `Stop-ScheduledTask`/cierres abruptos), y como la política de la tarea es `MultipleInstances: IgnoreNew`, cualquier intento nuevo se quedaba en cola esperando a que esa instancia fantasma "terminara" — cosa que nunca iba a pasar.
- Se intentó corregir la política a `StopExisting` (mata cualquier instancia previa antes de lanzar una nueva) pero el cmdlet `New-ScheduledTaskSettingsSet -MultipleInstances` de esta versión de PowerShell sólo acepta `Parallel`, `Queue`, `IgnoreNew` — `StopExisting` no está expuesto ahí aunque sí es válido en el XML/COM subyacente; ese cambio no se pudo aplicar por esta vía.
- **Arreglo que sí funcionó**: `Disable-ScheduledTask -TaskName "SuperCocina Print Agent"` seguido de `Enable-ScheduledTask -TaskName "SuperCocina Print Agent"` limpia el registro interno de "instancia corriendo" de Task Scheduler sin pedir contraseña ni tocar ninguna otra configuración. Después de eso, `Start-ScheduledTask` volvió a lanzar el agente con normalidad (confirmado con latido llegando a Lightsail, `is_online: True`).
- **Si este síntoma vuelve a aparecer** (la app dice "impresora no disponible", no hay proceso `python` corriendo en la Dell, y la Tarea Programada existe y está "Ready"/"Queued" pero no lanza nada): primero probar `Disable-ScheduledTask` + `Enable-ScheduledTask` + `Start-ScheduledTask` antes que cualquier otro diagnóstico más profundo, es la causa más probable y la más rápida de descartar.
- Detalle aparte descubierto en el camino (ya resuelto, documentar para no repetir la confusión): un intento de capturar la salida de la tarea redirigiéndola a un archivo (`run_agent.bat` con `>> agent.log 2>&1`) falló las primeras veces porque el archivo se creó con `Set-Content` estando parado en `C:\Users\lleva` en vez de `C:\SuperCocina\print-agent\dell_agent`, y la tarea apuntaba a la ruta correcta donde el archivo aún no existía — un recordatorio de que en la sesión SSH de la Dell (que entra a `cmd.exe`, no PowerShell, salvo que se escriba `powershell` primero) es fácil perder de vista en qué carpeta real se está parado.
- El historial de Task Scheduler ya quedó activado permanentemente en esta Dell (`wevtutil sl .../Operational /e:true`), así que la próxima vez que algo similar ocurra ya no hace falta activarlo de nuevo, sólo consultarlo directamente.
- Confirmado por el desarrollador (2026-09-21): tras este arreglo, una impresión real desde la app sí llegó a salir impresa en la POS-80 física. Con esto, todo el flujo de la estación de impresión (latido, expiración de trabajos, arranque automático por Tarea Programada, e impresión real) queda verificado de punta a punta en producción.
- **Ajuste adicional el mismo día**: la Tarea Programada (apuntando a `run_agent.bat`, que redirige la salida de `agent.py` a `agent.log`) abría una ventana de `cmd.exe` visible al iniciar sesión. Aunque se veía vacía (por la redirección), representaba un riesgo real: cualquiera podía cerrarla sin saber qué era y matar el servicio de impresión (confirmado por el desarrollador: al cerrar esa ventana, la siguiente impresión falló con "el servicio no está funcionando"). Corregido lanzando el `.bat` a través de un script `.vbs` con `WScript.Shell.Run(..., 0, False)` (estilo de ventana `0` = oculta), y apuntando la acción de la tarea a `wscript.exe run_agent_hidden.vbs` en vez de al `.bat` directamente. Con esto el agente arranca sin ninguna ventana visible; confirmado por el desarrollador que ya no aparece ninguna terminal al iniciar sesión y que la impresión sigue funcionando.
- Ruta final de los archivos de arranque en la Dell: `C:\SuperCocina\print-agent\dell_agent\run_agent.bat` (invoca python y redirige a `agent.log`) y `C:\SuperCocina\print-agent\dell_agent\run_agent_hidden.vbs` (lanza el `.bat` oculto); la Tarea Programada `"SuperCocina Print Agent"` apunta a este último. Si en el futuro hay que depurar un problema del agente, revisar primero `agent.log` (tiene toda la salida que antes se veía en consola) antes de asumir que hace falta correrlo manualmente.
- No se tocó `EmployeeLoginForm` (login normal completo con selector de perfil) ni el resto de roles (Administrador, Telefonista, Repartidor); el cambio es exclusivo de meseros, igual que el sistema de PIN que reemplaza.

## Corrección: ticket de Mesas comprimido (1 línea visible) en Galaxy Tab A9+ horizontal, mientras Pedidos se veía bien (2026-09-21)

- Reportado por el desarrollador: en `/app/mesas/cuentas/<id>/` en Tab A9+ horizontal, el panel del ticket se comprimía a su contenido mínimo — se alcanzaba a ver apenas 1 artículo con su propio scroll diminuto, sin poder leer el ticket completo. En `/app/pedidos/<id>/editar/`, en el mismo dispositivo/orientación, el ticket sí se veía bien (varias líneas visibles). En local (iPad mini/iPad air) el desarrollador no reproducía el problema, sólo en el dispositivo real desplegado.
- Diagnóstico hecho con Playwright (autorizado explícitamente por el desarrollador para este caso, igual que para el bug del huevo opcional), emulando el viewport CSS real de Tab A9+ horizontal (1280×800, táctil) contra un servidor local con datos reales, comparando en vivo el `getComputedStyle`/`getBoundingClientRect` del `<aside class="table-ticket">` de Mesas contra el `<aside class="internal-live-ticket">` de Pedidos.
- Causa raíz confirmada con medidas exactas: el panel de Mesas medía sólo 364px de alto (contra 768px — el alto real disponible del viewport — que sí alcanzaba Pedidos) y su lista de artículos (`.table-ticket-items`) tenía `flex: 0 1 auto` (sin crecimiento) en vez de `flex: 1 1 4.5rem` que sí tenía la de Pedidos. La regla unificada que ya existía en el archivo (agregada en la corrección del 2026-09-18, "Ticket de altura estable", la que usan tanto Mesas como Pedidos) fija `height: calc(100dvh - 2rem)` y `flex: 1 1 4.5rem` — pero **dos copias más antiguas y exclusivas de Mesas**, ambas con `!important` (una con el comentario "Ticket de Mesas coherente en todos los tamaños" cerca del inicio del archivo, y una segunda casi idéntica más adelante con el comentario "Prioridad final del ticket de Mesas" — un intento previo, aparentemente de otra IA, de "ganar" la cascada repitiendo el mismo problema en vez de corregirlo), forzaban `max-height: calc(100dvh - 18rem)` (=512px exactos a 800px de alto — coincidió perfecto con lo medido) y `height: auto`, además de `flex: 0 1 auto !important` en la lista. Por tener `!important`, estas dos reglas exclusivas de Mesas le ganaban a la regla unificada sin importar el orden, y como nunca existieron para `.internal-live-ticket`, Pedidos nunca sufrió el problema.
- Corrección: se quitaron únicamente las propiedades en conflicto (`height`/`max-height` del panel, `flex` de la lista de artículos) de ambas copias exclusivas de Mesas, dejando intactas el resto de sus propiedades (que sí siguen siendo necesarias y no compiten con nada: `display:flex`, `overflow:hidden`, el grid interno de cada artículo, el tamaño de los botones de cantidad). Con eso, la regla unificada (que ya funcionaba bien para Pedidos) queda libre para gobernar también el alto y el crecimiento de Mesas.
- Verificado con Playwright antes/después: el panel de Mesas pasó de 364px/82px (panel/lista) a 768px/486px, igualando exactamente el comportamiento de Pedidos (768px de panel). Confirmado también visualmente con una captura de pantalla a 1280×800. Se ejecutó la suite completa (78 pruebas) sin fallos; no se requirió migración (cambio puramente CSS).
- Nota para el futuro: si un bug de layout parece "sólo pasar en Mesas pero no en Pedidos" (o viceversa) pese a que ambos comparten la misma regla CSS "unificada" en teoría, sospechar primero de una regla vieja, exclusiva de uno de los dos, con `!important`, que nunca se limpió tras agregar la regla unificada — buscar duplicados del mismo selector/comentario antes de asumir que hace falta escribir una regla nueva.
- Detalle aparte descubierto en el camino: la base de datos local de desarrollo tenía pendiente la migración `accounts.0004_remove_profile_pin_failed_attempts_and_more` (la del cambio de PIN a contraseña diaria de hace unos días) — nunca se había corrido `migrate` localmente después de esa migración, lo que causaba un `IntegrityError` al crear cualquier usuario nuevo desde `manage.py shell`. Se aplicó (`python manage.py migrate accounts`). Si `manage.py shell` truena creando un usuario con un error de `quick_pin_hash`/NOT NULL, es señal de que faltan migraciones locales por correr, no un bug de código.
- Confirmado por el desarrollador en el dispositivo físico (Tab A9+) tras desplegar a producción. Causa real de que "no funcionara" al probar por primera vez: `templates/base_internal.html` sigue cargando `app.css?v=235` — Cloudflare/el navegador cachean el CSS por esa URL exacta; como el número de versión nunca cambió, seguían sirviendo la versión vieja del archivo pese al contenido correcto en el servidor. Se subió a `?v=236`. **Lección para el futuro: cualquier cambio a `static/css/app.css` (o cualquier estático con `?v=` en su URL) debe ir acompañado de subir ese número en `templates/base_internal.html`, o el cambio nunca llegará a los dispositivos reales pese a estar bien desplegado en el servidor.**

## Actualización: tres correcciones de UI para celular + lección sobre servidores locales duplicados (2026-09-21)

- Pedido del desarrollador, con capturas de referencia: (1) quitar el aviso "Ahora está operando X" que aparecía en pantalla cada vez que un mesero usa "Cambiar mesero", ya que el nombre del perfil activo siempre está visible arriba; (2) en `/app/pedidos/<id>/editar/`, el botón que cambia entre "Modo comida"/"Modo desayuno" se salía de la pantalla en iPhone 12 y iPhone SE; (3) en Mesas, el formulario de Comida corrida/Comida ejecutiva debía reacomodar Agua/Refill extra+Lleva bolillo/Huevo opcional en 3 columnas iguales (agua, refill+bolillo apilados, huevo), con el campo de comentario abajo a todo lo ancho, en vez de 5 tarjetas apiladas una tras otra.
- **(1)** `accounts/views.py:quick_switch` — se quitaron las dos llamadas a `messages.success(request, f"Ahora está operando...")` (una para el cambio instantáneo hacia un mesero que ya inició sesión hoy, otra para el primer cambio con contraseña). No se tocaron los mensajes de error (contraseña incorrecta, etc.), sólo los de éxito.
- **(2)** Causa raíz: `.internal-capture-heading` es una rejilla CSS de 6 columnas implícitas (flecha, título, modalidad, cliente, "Estado y seguimiento", switch de modo), pensada para escritorio; de las más de 15 reglas existentes para este mismo selector en anchos angostos, ninguna reduce ese número de columnas (sólo ajustan fuente/relleno), así que las 6 seguían intentando caber en una sola fila y la última se salía. Corrección (agregada al final de `app.css`, no se borró nada viejo): se saca `.capture-heading-actions` de la rejilla de 6 columnas y se le da su propia fila completa con `display:flex` interno.
- **(3)** Se agregó una clase nueva sin ninguna otra regla en el archivo, `table-package-refill-bread-group`, envolviendo Refill extra + Lleva bolillo en `tables/templates/tables/table_detail.html` — antes ese envoltorio (con la clase histórica `table-package-stacked-rules`, que tiene más de 20 reglas atadas sólo a Comida ejecutiva) sólo existía para Comida ejecutiva; ahora existe siempre, con AMBAS clases en Comida ejecutiva (para no perder su comportamiento previo en otros anchos) y sólo la nueva en Comida corrida. La regla CSS nueva (al final del archivo) tuvo que usar selectores con la especificidad más alta encontrada en el archivo para este elemento (combinando `.package-visual-groups >` y `form[data-package-form][data-package-kind="running/executive"]` a la vez, con la clase del diálogo duplicada `.table-visual-package-dialog.table-visual-package-dialog` como refuerzo) para poder ganarle a las reglas de una sola columna agregadas en la corrección del huevo opcional del 18/19 de septiembre — de lo contrario perdía pese a estar al final del archivo, porque tenía MENOS clases en la cadena del selector que las reglas viejas.
- **Lección de especificidad (recurrente en este archivo, ya iba dos veces esta semana)**: cuando una regla nueva con `!important` pierde contra una vieja también con `!important` pese a estar después en el archivo, casi siempre es que la vieja tiene más clases/atributos en la cadena del selector. Contar selectores explícitamente (o revisar con `getComputedStyle` en vivo) antes de asumir que "estar al final" basta.
- **Pendiente explícito, reconocido ante el desarrollador**: para (2) y (3) NO se borró ninguna regla vieja — sólo se agregaron reglas nuevas con más especificidad al final del archivo, seguiendo el mismo patrón de "apilar en vez de limpiar" que el desarrollador identificó como el problema de fondo de este archivo (sospecha, muy probablemente correcta, de que otra IA fue agregando parches sin borrar versiones anteriores según cambiaba el diseño). Las 15+ reglas viejas de `.capture-mode-switch`/`.internal-capture-heading` y las 20+ de `.table-package-stacked-rules`/`.table-package-visual-extras` siguen en el archivo, ahora muertas (superadas por las nuevas), pendientes de una limpieza real que el desarrollador pidió explícitamente hacer más adelante, con cuidado, sin romper nada — no se acordó aún el alcance exacto de esa limpieza.
- **Lección operativa importante — servidores de desarrollo local duplicados**: durante la verificación con Playwright de (3), los resultados salían inconsistentes (a veces reflejaba el HTML viejo pese a que el archivo en disco y hasta `manage.py shell`/`django.test.Client` ya mostraban el cambio correcto). Causa: había SIMULTÁNEAMENTE hasta 4 procesos `manage.py runserver 127.0.0.1:8000` corriendo — 2 del agente (terminal `.venv` del proyecto) y 2 del desarrollador (su propia terminal, con el Python de Anaconda `D:\Users\bauti\anaconda3\python.exe`, probablemente dejados abiertos de sesiones de prueba anteriores). En Windows sólo UN proceso puede enlazarse de verdad a un puerto; el que "ganaba" el puerto 8000 no siempre era el más reciente, así que las pruebas del agente a veces golpeaban un proceso viejo del desarrollador sin que nadie lo notara. Un proceso incluso se "reapareció" solo tras matarlo (probablemente el autoreload de Django relanzando un hijo). **Para el futuro: antes de depurar "por qué mis cambios no se reflejan" en local, verificar primero cuántos procesos `runserver` compiten por el mismo puerto** (`Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Select ProcessId,CommandLine` en PowerShell) en vez de sospechar de caché de Django/plantillas. La solución práctica que se usó: matar todos los procesos duplicados y, para evitar volver a pelear por el mismo puerto, correr las pruebas del agente en un puerto distinto (8001) al que normalmente usa el desarrollador (8000).
- Se ejecutó la suite completa (78 pruebas) sin fallos. No se requirió migración. Verificado visualmente con Playwright a 390×844 (iPhone 12) contra un servidor local limpio (puerto 8001, sin el conflicto de procesos): el switch de modo ya no se sale de pantalla, y el diálogo de Comida corrida/ejecutiva muestra las 3 columnas correctas con el comentario abajo a todo lo ancho. Pendiente de confirmación manual del desarrollador en dispositivos reales y en producción.
- **Dos ajustes adicionales el mismo día, tras revisión visual del desarrollador con capturas reales**: (a) en el diálogo de paquetes, la columna de "Huevo opcional" quedaba visiblemente más corta que las de Agua y Refill+Bolillo (dejando un hueco vacío abajo), porque las tres columnas usan `grid-row: 1 / span 2` pero ninguna tenía `align-self`/`height` explícitos y algo más adelante en el archivo anulaba el `stretch` por defecto sólo para el huevo; se agregó `height: 100% !important; align-self: stretch !important;` a las tres (agua, envoltorio refill+bolillo, huevo) para que las tres midan siempre lo mismo. (b) en el encabezado de Pedidos, tras sacar "Estado y seguimiento" + el switch de modo a su propia fila con `display:flex`, quedaban apilados uno encima del otro en vez de lado a lado, pese a que la fila tenía espacio de sobra (141px de contenido en 381px disponibles); causa: una regla ya existente sin relación aparente, `@media (max-width: 820px) { .capture-heading-actions { flex-direction: column; } }`, seguía aplicando porque la regla nueva nunca declaraba `flex-direction` (no hacía falta especificidad para ganar, simplemente nadie más lo estaba peleando); se agregó `flex-direction: row !important` a la regla nueva. Ambos verificados con Playwright (alturas iguales en las 3 columnas; "Estado y seguimiento" y el switch en la misma fila, sin desbordar) y visualmente con capturas. Se re-ejecutó la suite completa (78 pruebas) sin fallos.
- Nota para el futuro: cuando una regla nueva con `!important` gana la "pelea" de especificidad mostrada en `getComputedStyle` pero el resultado visual sigue mal, revisar si la regla nueva simplemente **no declaró alguna propiedad relevante** (como `flex-direction` o `align-self`) — una regla vieja sin `!important` y sin ninguna relación temática obvia puede seguir ganando esa propiedad específica por default, sin necesidad de "pelear" con la nueva.
- **Ajuste final el mismo día**: el desarrollador pidió además (a) centrar verticalmente el texto/control de "Huevo opcional" dentro de su tarjeta (se agregó `justify-content: center !important` a la regla ya existente, que ya era `display:flex; flex-direction:column`), y (b) que Comida corrida usara el mismo tamaño compacto que ya se veía en Comida ejecutiva para las tarjetas de Agua/Refill+Bolillo/Huevo — antes usaban `height:100%` sobre un renglón de grid con `grid-template-rows: auto auto`, lo cual es ambiguo (un porcentaje de un renglón "auto" no tiene una base fija para resolver) y por eso el alto terminaba dependiendo de diferencias sutiles de contenido entre ambos formularios (auto-medía distinto: 214px en Corrida vs 104px en Ejecutiva). Se cambió a un alto fijo explícito para ambos renglones (`grid-template-rows: 5.75rem 5.75rem`, calculado para respetar el `min-height: 92px` que ya tiene cada `.product-rule-card` en su regla base — un primer intento con `3.25rem` cada uno recortó visualmente "Lleva bolillo" por quedar debajo de ese mínimo). Verificado con Playwright: ambos formularios ahora miden exactamente lo mismo (sin recortes) y el huevo queda centrado. Se re-ejecutó la suite completa (78 pruebas) sin fallos.
- **Aclaración importante para depurar overflow en local de aquí en adelante**: el desarrollador reportó que el desbordamiento del switch de modo en Pedidos "seguía fallando" tras el arreglo, pero su captura mostraba la URL `127.0.0.1:8000` — un proceso `runserver` DISTINTO al que usa el agente para verificar (`127.0.0.1:8001`, ver la sección de arriba sobre servidores duplicados). Las comprobaciones automatizadas contra 8001 no encontraron overflow. Antes de asumir que un arreglo de CSS/plantilla no sirvió en local, confirmar primero que la prueba se hizo contra el mismo puerto/proceso donde se verificó el cambio.
- **La verdadera causa del desacuerdo sobre "la barra" de Pedidos**: el desarrollador se refería a los 6 elementos visuales de arriba como una sola barra (regreso, título, Recoger, Domicilio, Cliente, Estado y seguimiento, switch), pero en el HTML estático sólo 2 de esos (regreso+título, estado+switch) viven dentro de `.internal-capture-heading` — "Recoger"/"Domicilio" (`.command-group`) y "Cliente" (`.customer-command`) en realidad pertenecen a `.internal-command-bar`, una sección aparte más abajo en el DOM. `internal-order-form.js` (línea ~36-44) los **mueve dinámicamente** con JavaScript adentro del encabezado al cargar la página (`headingActions.before(modalityCommand, customerCommand)`) y oculta la sección original — por eso se ven como una sola barra continua en pantalla aunque el arreglo anterior (que sólo tocaba "Estado y seguimiento" + el switch) no resolvía el cuadro completo. Lección: cuando algo se ve "junto" en pantalla pero el análisis del HTML estático no cuadra con lo que se ve, sospechar de manipulación del DOM vía JavaScript después de la carga, no sólo de CSS.
- El desarrollador aclaró además que el objetivo no era "que no se salga de la pantalla" (lo cual ya se cumplía con el diseño de 2 filas) sino literalmente **que los 6 elementos quepan en una sola fila**, sin bajar a una segunda. Se reescribió la regla del encabezado por completo: ícono solo (sin texto "Pedidos") para el botón de regreso, título con elipsis y sin subtítulo, "Modalidad"/"Cliente" sin su etiqueta de texto (sólo iconos/valor), el nombre del cliente con `max-width` y elipsis (para no depender de qué tan corto sea "Mostrador"), y "Estado y seguimiento" reducido a una píldora angosta con elipsis en vez de su texto completo. Probado con Playwright con un nombre de cliente artificialmente largo ("Guadalupe Montenegro de la Torre Hernandez") en 390px, 375px y hasta 360px de ancho (un Android angosto) sin que nada se desborde nunca. Se ejecutó la suite completa (78 pruebas) sin fallos.
- **Dos ajustes finales de pulido el mismo día**: (a) el botón de "Cliente" en ese mismo encabezado compacto mostraba 2 líneas (nombre + "Revisar entrega/datos"), quedando más alto que sus vecinos y rompiendo el centrado vertical de toda la fila; se ocultó la segunda línea (`small`) y se centró el botón (`display:flex; align-items:center; justify-content:center`) para que quede en una sola línea, igual de alto que los demás. (b) Un bug totalmente aparte y preexistente (no relacionado a los cambios de esta sesión) en `/app/pedidos/` (la LISTA de pedidos, no la de captura): el encabezado `.page-heading` con `<h1>Pedidos</h1>` quedaba tapado visualmente por los botones "Recoger"/"Entrega a domicilio" (296px los dos juntos, muy anchos para el poco espacio que le dejaban a la columna del título en una rejilla `minmax(0,1fr) auto`) — el texto no cabía en su columna pero seguía dibujándose por encima de la columna vecina, quedando debajo de los botones por orden de pintado (`main:has(.order-board-columns) > .page-heading` en `app.css`, sin relación con `.internal-capture-heading`). Corregido bajando esos dos botones a su propia fila completa en `max-width: 480px`, en vez de seguir achicando texto/relleno. Verificado con Playwright y capturas; se ejecutó la suite completa (78 pruebas) sin fallos.
- **Dos correcciones más el mismo día, tras feedback adicional**: (a) en `/app/pedidos/` el desarrollador prefirió que "← Pedidos"/"Pedidos"/Recoger/Entrega a domicilio quepan los 4 en una sola fila (no en 2 como el intento anterior) — se rediseñó a `display:flex` en una sola fila, con los botones "Recoger"/"Entrega a domicilio" reducidos a sólo ícono (ocultando el `<span>` de texto) para que siempre quepan, igual que ya se había hecho para el switch modo comida/desayuno del otro encabezado. (b) en el encabezado compacto de captura de un pedido individual, el texto "Capturar 1709004" quedaba pegado hacia abajo en vez de centrado verticalmente junto al ícono de regreso; causa: varias reglas viejas y dispersas ya ponían `align-self: end` en `.internal-capture-heading > div:first-child > h1` (una incluso sin relación aparente con el breakpoint móvil), y la regla nueva nunca había declarado `align-self`; se agregó `align-self: center !important`. Verificado con Playwright y capturas; se ejecutó la suite completa (78 pruebas) sin fallos.
- Patrón que se repitió varias veces hoy con este mismo encabezado: una regla nueva con `!important` puede ganar la especificidad para las propiedades que SÍ declara, pero cualquier propiedad que NO declare sigue en manos de reglas viejas y dispersas (`flex-direction`, `align-self`, etc.) — antes de dar por bueno un ajuste visual, revisar con `getComputedStyle` cada propiedad de posicionamiento/alineación relevante, no sólo las que se acaban de tocar.

## Corrección: campo "Otra cantidad" apretado en el panel de Efectivo, sólo en escritorio (2026-09-21)

- Reportado por el desarrollador únicamente para escritorio en `/app/pedidos/<id>/editar/`: al elegir Efectivo, el campo "Otra cantidad" se veía mal — la etiqueta partida en 2 líneas y el recuadro de captura casi invisible. Pidió explícitamente cuidar no mover el comportamiento de ninguna otra pantalla, ya que todas las demás ya se comportaban como quería.
- Causa raíz: `.internal-live-ticket .ticket-payment-details .cash-command-buttons { grid-template-columns: repeat(3, minmax(0, 1fr)); }` (línea ~6079) — una regla **sin ninguna media query**, aplica siempre, pensada para el panel de efectivo que aparece dentro del ticket de Pedidos (un sidebar angosto incluso en escritorio). Con 7 elementos (5 montos rápidos + "Pago exacto" + "Otra cantidad") repartidos en sólo 3 columnas iguales, "Otra cantidad" terminaba en una sola columna de ~118px.
- Corrección: se le da a `.cash-custom-choice` su propia fila a todo lo ancho (`grid-column: 1 / -1`) **sólo dentro de `@media (min-width: 901px)`** — a propósito, para no tocar ninguna de las reglas móviles/táctiles existentes que ya resuelven esto de otra forma para pantallas angostas (confirmado con Playwright: en 390px el campo sigue midiendo lo mismo que antes, sin cambios). No se tocaron los montos rápidos ($20-$500) ni "Pago exacto".
- Verificado con Playwright: en escritorio (1440px) el campo pasó de 118px a 368px de ancho (el input de 25px a 255px); en celular (390px) nada cambió. Se ejecutó la suite completa (78 pruebas) sin fallos; no se requirió migración.

## Corrección: ticket ilegible al elegir Efectivo en Pedidos (Tab A9+ horizontal) + huevo opcional sobre el ticket (2026-09-21)

- Reportado por el desarrollador, con captura en local a 1280×800 (Tab A9+ horizontal): en `/app/pedidos/<id>/editar/`, al elegir Efectivo como método de pago, la lista de artículos del ticket "no se aparecía" — no dejaba ver qué se había agregado, como si el scroll no existiera. También reportó que el "Huevo opcional" de Comida corrida/ejecutiva (el panel inline de Pedidos, distinto al diálogo modal de Mesas ya corregido antes) se sobreponía visualmente sobre el panel de "Método de pago" del ticket.
- **Causa del ticket**: al elegir Efectivo, `.ticket-payment-details` (los 5 montos rápidos + "Pago exacto" + "Otra cantidad") se inserta dentro del ticket y mide ~309px de alto — pero como no es la lista de artículos, cae en la regla `flex: 0 0 auto` ("nunca se encoge") que ya se usaba para elementos fijos pequeños (total, botones de imprimir). Al no tener límite de altura, este panel se comía casi todo el espacio del ticket (que sólo tiene 768px totales en esta tablet), dejándole a la lista de artículos apenas 21px — invisible en la práctica.
- Corrección (dentro del mismo bloque `@media (pointer: coarse) and (orientation: landscape) and (max-height: 900px)` que ya compacta el resto del ticket en tablets cortas): se le da a `.ticket-payment-details` su propio límite (`max-height: 36dvh; overflow-y: auto`) para que, si no cabe, haga scroll por su cuenta en vez de desplazar a los artículos; se compactan también sus botones internos ($20-$500, Pago exacto, Otra cantidad) a un tamaño más chico; y se le pone a la lista de artículos un `min-height: 7.5rem` para garantizar que siempre se vea al menos un par de líneas. Verificado con Playwright: la lista pasó de 21px a 149px de alto, ya mostrando artículos reales (`1 × Enchiladas Verdes`).
- **Causa del huevo sobre el ticket**: `.auto-package-options` (el panel de Agua/Acompañamiento/Frijoles/Huevo de Comida corrida y ejecutiva EN PEDIDOS, dentro de `.internal-menu-workspace`) exige 4 columnas con anchos mínimos que suman 866px — pero en Pedidos esa columna comparte pantalla con el ticket (sidebar fijo), así que a 1280px de ancho total sólo le quedan ~827px reales. Como nada recorta el desborde, la última columna (el huevo) se dibujaba fuera de su propio contenedor, encima del ticket. Ya existía una regla que compacta esto a 3 columnas, pero su punto de quiebre (`max-width: 1080px` de ancho TOTAL de pantalla) nunca contempló que el ticket le resta espacio real a esta columna — 1280px de pantalla total no dispara esa regla aunque el espacio disponible real sea menor que en un monitor angosto de 1080px sin ticket.
- Corrección: se extendió el mismo compactado de 3 columnas a un nuevo rango `(min-width: 1081px) and (max-width: 1300px)`, cubriendo tablets como la Tab A9+. Se descartó que esto afectara Mesas (`.auto-package-options` sólo existe en las plantillas de Pedidos). Tuvo que llevar `!important` porque existe otra regla SIN ninguna media query (línea ~2542, con valores fraccionarios `minmax(145px,.9fr)...`) que sin `!important` seguía ganando por estar más adelante en el archivo pese a que la nueva regla sí aplicaba (confirmado con `matchMedia` + inspección directa de `document.styleSheets`, no sólo `getComputedStyle`, para saber CUÁL regla exacta estaba ganando entre más de 10 candidatas para el mismo selector).
- Se subió `app.css?v=236` a `?v=237` en `base_internal.html` (iba acumulado bastante desde el último aviso de este mismo problema de caché). Se ejecutó la suite completa (78 pruebas) sin fallos; no se requirió migración.
- Nota para el futuro: cuando una regla nueva "gana" según `getComputedStyle` de una propiedad pero el resultado visual sigue sin coincidir con lo esperado, y no hay una explicación obvia (como `flex-direction`/`align-self` no declarados), iterar `document.styleSheets` en vivo listando CADA regla que matchea el selector con `element.matches(selectorPart)` y `window.matchMedia(...).matches`, no confiar sólo en `getComputedStyle` del resultado final — con 10+ duplicados del mismo selector en este archivo, adivinar cuál gana por lectura manual es poco confiable.
- Nota para el futuro (patrón, van 3 veces esta semana): varias secciones de Pedidos ajustan su layout según el ancho TOTAL del viewport (`@media (max-width: Npx)`), sin contemplar que el ticket sidebar siempre le resta ~380-400px de espacio real a la columna principal. Un breakpoint pensado para "una pantalla angosta sin sidebar" (ej. 1080px) no cubre "una pantalla ancha CON sidebar" que en la práctica deja el mismo espacio disponible (ej. 1280px con ticket ≈ 880px sin ticket). Antes de descartar un breakpoint por parecer "suficientemente ancho", medir el espacio real disponible de la columna en cuestión, no el ancho total de pantalla.

## Corrección: la Tarea Programada del agente de impresión dependía de iniciar sesión de Windows, no de prender la Dell (2026-09-22)

- Reportado por el desarrollador: la Dell y la POS-80 estaban encendidas desde las 8:00 a. m., pero al intentar imprimir cerca de las 10:00 a. m. la app respondía "la impresora no está disponible ahora mismo".
- Diagnóstico hecho a distancia (el agente no tiene ni tendrá acceso directo a la Dell ni al servidor de Lightsail en esta relación de trabajo: el desarrollador ejecuta cada comando que se le pasa y pega la salida de vuelta). `Get-Process python` mostró que el proceso del agente (`C:\SuperCocina\print-agent\dell_agent\.venv\Scripts\python.exe`) tenía `StartTime` de las 10:22:27 a. m. — es decir, nunca estuvo corriendo desde las 8:00, arrancó justo cuando el desarrollador abrió PowerShell para correr los diagnósticos. `Get-Printer`/`Get-PnpDevice` confirmaron que Windows sí veía la POS-80 como `Normal`/`OK` (no era un problema de la impresora física), y una llamada manual a `POST /app/impresion/agente/latido/` con `Invoke-WebRequest` respondió `200 {"ok":true}` (el token y la conectividad HTTPS hacia Lightsail tampoco eran el problema).
- Causa raíz: la Tarea Programada `"SuperCocina Print Agent"` seguía usando el disparador `AtLogOn` (ver README de `dell_agent`, preparación paso 5), que sólo se activa con un inicio de sesión interactivo real (escribir la contraseña/PIN de Windows), no con que el equipo esté encendido y la pantalla de bloqueo visible. Como nadie había tecleado credenciales en esa Dell desde las 8:00 (la pantalla sólo estaba encendida/bloqueada), la tarea nunca se disparó hasta que el desarrollador inició sesión para abrir PowerShell.
- Se evaluó primero una hipótesis de "dos perfiles de Windows distintos" (una cuenta operativa vs. la usada para diagnosticar); el desarrollador la corrigió: sólo existe la cuenta "lleva" en esa Dell, así que el problema era puramente encendido-vs-sesión-iniciada, no una tarea atada al perfil equivocado.
- Arreglo aplicado: se recreó la tarea con disparador `AtStartup` (arranca con el sistema operativo, sin depender de ningún inicio de sesión) y ejecutándose como `SYSTEM` (`-RunLevel Highest`, sin credenciales de usuario). Se intentó primero mantener la cuenta "lleva" con `LogonType Password` (contraseña real de su cuenta Microsoft `llevatucomida1047@gmail.com`), pero falló repetidamente con `0x8007052e` ("user name or password incorrect") — muy probablemente por verificación en dos pasos o "cuenta sin contraseña" activada en esa cuenta Microsoft; se descartó esa vía en favor de `SYSTEM`, que no requiere credenciales y evita por completo ese problema.
- Como `PRINT_AGENT_TOKEN`, `PRINT_SERVER_URL` y `PRINT_PRINTER_NAME` estaban guardadas como variables de entorno de **Usuario** (sólo visibles para "lleva"; ver README de `dell_agent`, preparación paso 4), se copiaron también a nivel **Sistema** (`[Environment]::SetEnvironmentVariable(..., "Machine")`) para que el proceso corriendo como `SYSTEM` las siga viendo. **`print_station/dell_agent/README.md` no se actualizó todavía para reflejar este cambio (sigue describiendo el flujo `AtLogOn`/variables de Usuario) — pendiente de corregir ese README para que no confunda una futura reinstalación.**
- Verificado en la sesión: la tarea quedó registrada (`State: Ready`), se lanzó manualmente con `Start-ScheduledTask` y apareció un proceso `python.exe` nuevo bajo la ruta correcta del `.venv`. Se detectaron y cerraron dos procesos huérfanos que habían quedado corriendo desde el intento anterior (arrancado por `AtLogOn` antes de borrar esa tarea), para no dejar dos agentes reclamando trabajos a la vez (no es peligroso por el `select_for_update(skip_locked=True)` de `claim_job`, pero es innecesario).
- **Pendiente explícito, no verificado todavía en esta sesión**: una prueba real de apagar/prender la Dell por completo SIN iniciar sesión de Windows y confirmar que un ticket se imprime solo. El desarrollador lo dejó pendiente para más tarde.
- Nota para el futuro: si "la impresora no está disponible" vuelve a reportarse justo después de prender la Dell (no horas después), sospechar primero de si alguien realmente iniciar sesión de Windows en esa Dell, antes de revisar latido/token/impresora física — `Get-Process python` con un `StartTime` que no coincide con la hora de encendido reportada es la señal más rápida de descartar esto.

## Corrección: "Comida por orden" sólo dejaba agregar un tipo de pieza de pollo (pierna o muslo), nunca ambos desde el mismo botón "+" (2026-09-22)

- Reportado por el desarrollador: al pedir en Comida por Orden 2 piernas y 1 muslo del guisado de pollo del día usando el botón "+" del catálogo (no el "+" del ticket), la app sólo dejaba agregar un tipo de pieza — la segunda vez que se pedía la otra pieza, seguía agregando en silencio la primera elegida.
- Causa raíz en `static/js/internal-order-form.js`: el manejador de envío para `form[data-internal-add]` (usado por "Comida por Orden") sólo abre el diálogo de elegir pierna/muslo cuando el input oculto `chicken_piece` está vacío (línea ~949); pero tras un envío exitoso nunca lo volvía a vaciar (a diferencia del formulario hermano `data-internal-auto-add`, usado en Comida Corrida, que sí hace `chickenField.value = ""` en su bloque `finally`). Por eso, tras elegir una pieza una vez, el campo quedaba fijo con ese valor y cada click subsecuente de "+" en esa misma tarjeta reenviaba la misma pieza sin volver a preguntar.
- El botón "+" del ticket (sumar una unidad más a una línea ya agregada, vía `change_url`/acción `increase`) usa un camino de código totalmente distinto que nunca toca este campo, así que ya se comportaba correctamente (no debía volver a preguntar) — no requirió cambios.
- Arreglo: se agregó `if (chickenField) chickenField.value = "";` al bloque `finally` del manejador de `data-internal-add` (junto a la limpieza que ya existía ahí), replicando el patrón ya usado en `data-internal-auto-add`. Con esto cada click de "+" del catálogo vuelve a preguntar pierna/muslo.
- Se subió `internal-order-form.js?v=40` a `?v=41` en `orders/templates/orders/internal_order_form.html`, siguiendo la lección de caché ya documentada esta semana (ver corrección del 2026-09-21 sobre `app.css?v=`) — sin subir la versión, este cambio no habría llegado a los dispositivos reales pese a estar bien desplegado.
- Verificado manualmente por el desarrollador en el navegador (preferencia general del proyecto: pruebas de UI manuales, no Playwright, salvo pedido explícito). No se requirió migración; cambio puramente de JavaScript.

## Actualización: Tarea Programada del agente de impresión vuelta a AtLogOn (2026-09-23)

- El día siguiente al cambio a `AtStartup`/`SYSTEM` (ver corrección del 2026-09-22), el desarrollador reportó de nuevo "la impresora no está disponible" en horario de servicio, urgente. Diagnóstico: el agente sí lograba reclamar el trabajo (el ticket llegaba a "enviado", en verde) pero fallaba al imprimir de verdad (pasaba a rojo/fallido). Causa muy probable: `agent.py::render_ticket()` usa Playwright para lanzar Edge y renderizar el ticket como imagen antes de mandarlo a la POS-80; Chromium/Edge no arranca de forma confiable corriendo como `SYSTEM` porque esa cuenta no tiene una sesión de escritorio interactiva real (aislamiento de Sesión 0 de Windows). Confirmado indirectamente: corriendo el mismo `agent.py` manualmente en una consola bajo el usuario "lleva" (sesión interactiva real), el mismo trabajo sí se imprimió sin error.
- Arreglo para salir del apuro inmediato: correr `agent.py` a mano en una consola de PowerShell (`cd C:\SuperCocina\print-agent\dell_agent; .\.venv\Scripts\python.exe agent.py`) mientras se resolvía de raíz. Con eso sí imprimió con normalidad.
- Arreglo definitivo: en vez de `SYSTEM`/`AtStartup`, se configuró **auto-inicio de sesión de Windows** para la cuenta "lleva" (`HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`: `AutoAdminLogon=1`, `DefaultUserName`, `DefaultPassword`, `DefaultDomainName`) y la Tarea Programada se volvió a registrar como estaba originalmente en el README (`-AtLogOn`, sin `-User` explícito ya que sólo existe una cuenta en esa Dell, `-RunLevel Highest`, corriendo como "lleva"). Con esto se resuelven los dos problemas a la vez: la Dell inicia sesión sola al prender (nadie necesita tocar el teclado, igual que con `SYSTEM`), pero corre en una sesión de usuario real donde Edge/Playwright sí funciona (igual que antes de todos estos cambios).
- **`print_station/dell_agent/README.md` quedó desactualizado otra vez** tras este cambio — describe el flujo `AtStartup`/`SYSTEM` del 2026-09-22, que ya no es el que está configurado. Pendiente de corregir para reflejar auto-inicio de sesión + `AtLogOn` (este mismo commit lo corrige).
- **Pendiente explícito, no verificado todavía**: la prueba real de apagar/prender la Dell por completo sin tocar el teclado, para confirmar que el auto-inicio de sesión efectivamente dispara la Tarea Programada. Se decidió no probarlo de inmediato para no arriesgar un corte de impresión en medio del servicio; queda para un momento de menor tráfico.
- Nota para el futuro: si "SYSTEM"/"servicio sin sesión" vuelve a parecer la solución más robusta para algo que use Playwright/un navegador headless en esta Dell, considerar primero que Chromium bajo `SYSTEM` (Sesión 0, sin escritorio interactivo) es una fuente conocida de fallos — probar explícitamente con una impresión real antes de dar el cambio por bueno, no sólo confirmar que el proceso arrancó.

## Corrección: lista de artículos del ticket en 0px de alto en Pedidos, solo en escritorio con Efectivo seleccionado (2026-09-23)

- Reportado por el desarrollador con capturas: en `/app/pedidos/<id>/editar/` en **escritorio** (mouse, pantalla ancha), al elegir Efectivo como método de pago, la lista de artículos del ticket se veía comprimida a un renglón con scroll diminuto — muy similar al bug de Tab A9+ horizontal ya corregido el 2026-09-21, pero esta vez en escritorio, no en tablet táctil. El desarrollador aclaró explícitamente que en Mesas el mismo escenario se ve bien, sólo falla en Pedidos.
- Diagnóstico con Playwright contra un servidor local (mismo commit que produccion, sin cambios locales en `app.css`): `.internal-live-ticket .ticket-payment-details` (el panel "¿Con cuánto paga?" con los botones $20-$500, Pago exacto, Otra cantidad) no tenía ningún límite de altura en escritorio — sólo existía un límite equivalente (`max-height: 36dvh`) dentro de `@media (pointer: coarse) and (orientation: landscape) and (max-height: 900px)`, exclusivo de tablets táctiles. En escritorio ese panel crecía libremente y dejaba `.internal-live-ticket > .table-ticket-items` en **0px** de alto real (confirmado con `getBoundingClientRect`), no sólo "chico".
- Comprobado que Mesas no sufre esto porque su ticket (`.table-ticket`) no muestra el método de pago durante la captura (eso ocurre en otro punto del flujo); por eso el arreglo se limitó a `.internal-live-ticket`, sin tocar `.table-ticket`.
- Corrección: nuevo bloque `@media (min-width: 901px) and (pointer: fine)` (exclusivo de escritorio con mouse, no afecta táctil/tablet ni el `max-width: 900px` de móvil) que replica el mismo patrón ya probado para tablet: `.internal-live-ticket > .table-ticket-items { min-height: 8rem !important; }` y `.internal-live-ticket .ticket-payment-details { max-height: 40vh !important; overflow-y: auto !important; flex-shrink: 0 !important; }`.
- Verificado con Playwright antes/después contra un pedido real de 3 artículos: la lista pasó de 0px a 128px de alto, mostrando los 3 artículos completos con sus controles. Se subió `app.css?v=237` a `?v=238` en `templates/base_internal.html` (lección de caché de esta semana). Se ejecutó la suite completa (78 pruebas) sin fallos.

## Ajuste el mismo día: el arreglo de 3 líneas empujaba "Guardar sin cerrar"/"Cerrar captura" fuera de vista (2026-09-23)

- El desarrollador pidió agrandar el mínimo de artículos visibles de 2 a 3 líneas (`min-height: 16.5rem`, calculado exacto: 3 × 80.36px de alto por artículo + 2 gaps de 10.4px). Con eso, luego reportó que en escritorio, al elegir Efectivo, los botones "Guardar sin cerrar" y "Cerrar captura y enviar al listado" quedaban empujados fuera de la vista.
- Medido con Playwright: `.internal-live-ticket` tiene una altura fija (`calc(100dvh - 2rem)`, 868px a 900px de viewport) con `overflow: hidden !important` propio — por diseño, sólo `.table-ticket-items` se desplaza internamente. Sumando la altura real de cada hijo (incluyendo separaciones entre ellos, no sólo el contenido) con 3 líneas de artículos y el panel de Efectivo abierto, el contenido necesita ~1056px — 188px más de lo que el panel puede mostrar. Aún reduciendo el panel de Efectivo a prácticamente 0px no alcanza a compensar: **3 líneas completas + panel de Efectivo abierto + botones siempre visibles sin ningún scroll no caben simultáneamente** en un panel de esa altura.
- En vez de exprimir el panel de Efectivo hasta volverlo inusable (o recortar los botones), se le agregó `overflow-y: auto !important` a `.internal-live-ticket` **sólo en el mismo bloque `@media (min-width: 901px) and (pointer: fine)`** — el panel completo ahora puede desplazarse como cualquier barra lateral cuando el contenido no cabe, en vez de depender únicamente del scroll interno de artículos. El panel de Efectivo quedó con `max-height: 12rem` (subido de la primera prueba de `9rem`, que tampoco alcanzaba).
- Verificado con Playwright: `overflow-y` computado pasó de `hidden` a `auto`, con ~188px de contenido desplazable; forzando el scroll del panel hasta el final, los botones de guardar/cerrar se vuelven alcanzables. No quedan recortados ni inaccesibles, sólo requieren un scroll corto dentro del panel del ticket (no de toda la página) en el caso específico de Efectivo abierto + 3 artículos.
- **Detalle de depuración importante para el futuro**: al intentar forzar `max-height` vía `element.style.maxHeight` desde JavaScript/consola para diagnosticar, no tuvo ningún efecto — porque un estilo inline normal **no le gana a una regla de hoja de estilos con `!important`** (sólo `element.style.setProperty(prop, valor, "important")` sí le gana). Si un cambio de estilo por consola "no hace nada" en este archivo, sospechar primero de esto antes de asumir que el elemento no es el correcto.
- Se subió `app.css?v=239` a `?v=240`. Se ejecutó la suite completa (78 pruebas) sin fallos; no se requirió migración.

## Agregado: método de pago en la comanda de cocina (2026-09-23)

- Pedido del desarrollador: mostrar el método de pago en el ticket de cocina, en una sola línea chica, sin darle espacio de más.
- `payment_method` ya llegaba armado (`"Efectivo"`/`"Terminal"`/`"Transferencia"`/`"Pendiente"`) en `order_print_context()` y `table_print_context()` (`config/printing.py`), sólo faltaba mostrarlo. Se agregó `<p><strong>Pago:</strong> {{ payment_method }}</p>` a `templates/printing/kitchen_ticket.html`, dentro de `.ticket-meta` (mismo tamaño de letra chico que "Tomó:", 15px, ya definido en `print-ticket.css`) — no se creó ningún estilo nuevo.
- Esta plantilla es compartida por **todos** los flujos de comanda de cocina (normal y "modificado", tanto Mesas como Pedidos, incluyendo lo que reclama el agente de la Dell vía `print_station/views.py`) — un solo cambio de plantilla cubre los cuatro casos, confirmado revisando cada vista que la usa (`orders/views.py`, `tables/views.py`, `print_station/views.py`).
- Verificado con `render_to_string` contra un pedido real: aparece "Pago: Efectivo" correctamente. Se ejecutó la suite completa (78 pruebas) sin fallos. No se requirió migración ni cambio de CSS/JS, así que no hace falta subir ningún `?v=`.

## Quitado: bloqueo automático por inactividad (2026-09-23)

- El desarrollador reportó que "cada equis tiempo se pone la pantalla para cambiar de mesero" y preguntó por qué. Se le explicó que es el bloqueo por inactividad agregado el 2026-09-19 (`static/js/quick-switch-idle.js`, 3 minutos sin tocar la pantalla) — no era un bug, era la función tal como se diseñó. El desarrollador pidió quitarlo por completo.
- Se borró `static/js/quick-switch-idle.js` (sin más referencias en el resto del proyecto, confirmado por búsqueda) y se quitó su `<script>` de `templates/base_internal.html`.
- **Se conservó a propósito** el botón manual "Bloquear tablet" (mismo formulario `data-quick-lock-form`, en el mismo bloque de `base_internal.html`) — el desarrollador se refería específicamente al bloqueo *automático* por inactividad, no al botón que alguien presiona a propósito. Ese botón es un `<form>` normal sin dependencia de JavaScript, así que sigue funcionando igual sin el script eliminado.
- No se tocó `accounts/middleware.py` (`QuickSwitchLockMiddleware`): sólo redirige a la pantalla de cambio de mesero cuando la sesión tiene la bandera de bloqueo activada (`LOCK_KEY`), y esa bandera sólo se activaba al enviarse el formulario de bloqueo — sin el temporizador de inactividad, nada la activa automáticamente. El botón manual "Bloquear tablet" sigue pudiendo activarla a propósito.
- Se ejecutó la suite completa (78 pruebas) sin fallos. No se requirió migración ni cambio de CSS, así que no hace falta subir ningún `?v=` (sólo se quitó una etiqueta `<script>` y se borró un archivo).

## Corrección: error "Unexpected token '<'" al agregar Agua del día a un paquete (2026-09-23)

- Reportado por el desarrollador: al armar Comida corrida/ejecutiva con "Agua" activado, la app mostraba una alerta del navegador `Unexpected token '<', "<!doctype "... is not valid JSON`. Ese mensaje es el síntoma clásico de que el `fetch().then(r => r.json())` del JS recibió una página HTML de error 500 de Django en vez del JSON esperado (las vistas de agregar paquete sólo capturan `ValidationError`, así que cualquier otra excepción se cae hasta la página de error genérica).
- Causa raíz, en `orders/services.py`: tres funciones (`add_internal_order_package` línea ~769, `create_public_cart_order` línea ~968, `create_public_package_order` línea ~1038) hacían `daily_menu.water_product.name` sin comprobar que `water_product` no fuera `None` — y `DailyMenu.water_product` es un campo opcional (`null=True, blank=True`, `menu/models.py`); nada impide publicar un menú del día sin agua configurada. Cuando eso pasa y alguien activa "Agua" al pedir, revienta con `AttributeError: 'NoneType' object has no attribute 'name'`.
- El mismo archivo ya tenía el patrón correcto en otro lugar (línea ~74, usado para descontar inventario): `(item.water_product or (daily_menu.water_product if daily_menu else None)) if item.with_water else None` — nunca se aplicó a estas tres funciones cuando se escribieron.
- Arreglo: se replicó el mismo patrón de verificación (`daily_menu.water_product.name if daily_menu.water_product else ""`) en las tres funciones. Con `water_product` vacío, el pedido ya no truena: simplemente queda sin nombre de agua registrado en esa partida (comportamiento razonable — no hay agua del día que anotar).
- Confirmado en la base de datos local que el menú de hoy (23/09/2026) sí tiene agua configurada (`Agua de horchata`), así que el reporte del desarrollador corresponde a otro día donde no se configuró — esto explica por qué el bug es intermitente y no reproducible "siempre".
- Verificado en aislado que la expresión corregida da `''` cuando `water_product` es `None` y el nombre correcto cuando sí existe, sin lanzar excepción. Se ejecutó la suite completa (78 pruebas) sin fallos; no se requirió migración ni cambio de CSS/JS.
- **Pendiente sugerido, no implementado** (fuera del alcance de este arreglo puntual): en vez de dejar la partida silenciosamente sin agua, se podría validar antes de guardar y mostrarle a quien administra el menú un error claro tipo "No hay agua del día configurada para hoy" cuando alguien intente pedir agua sin que el menú la tenga asignada — así se detectaría la configuración incompleta en vez de sólo evitar el error.
