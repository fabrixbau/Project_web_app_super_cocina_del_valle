<!--
NOTA TEMPORAL PARA APRENDIZAJE:
Este documento conserva el estado entre sesiones. Registramos el módulo inicial de menú
como implementado y pendiente de migración/revisión manual por el desarrollador.
Puedes borrar esta nota después de leerla.
-->

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
[~] Menú fijo (categorías y productos pendientes de validación manual)
[ ] Menú diario
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
efectivo, tarjeta, transferencia.

Pasarela:
no existe.
```

---

## 11. Cambios recientes

### Foundation

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

Módulo inicial de menú implementado en código; migración `menu.0001_initial` y revisión manual pendientes.

## Last completed

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

- Validación manual de categorías, productos, disponibilidad, permisos y catálogo público.

## Next

- Aplicar `menu.0001_initial` y validar manualmente categorías/productos.
- Después de aprobación, agregar opciones configurables y envases.
- Crear el primer superusuario administrador.

## Important decisions

- Ver sección 10.
- El desarrollo se realizará por bloques pequeños con notas didácticas temporales al inicio de cada archivo tocado, pruebas automatizadas y una guía de verificación manual al finalizar.

## Known issues

- Integración WhatsApp pendiente.
- Impresión POS-8360 pendiente de validar técnicamente.
- La matriz actual protege áreas generales; los permisos CRUD detallados se agregarán junto con cada módulo real.
- El módulo menú no fue validado automáticamente por decisión del desarrollador.

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
