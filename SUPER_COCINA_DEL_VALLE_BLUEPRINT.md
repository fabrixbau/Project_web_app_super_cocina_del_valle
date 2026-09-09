<!--
NOTA TEMPORAL PARA APRENDIZAJE:
Se documentaron modalidad previa, pago diferido para recoger y estados cíclicos con historial.
Se corrigió el menú diario: no usa listas libres, sino siete lugares obligatorios
organizados como 2 primeros + 2 segundos + 3 guisados. Borra esta nota.
-->

# Super Cocina del Valle — Blueprint funcional y técnico

> Documento base del proyecto.
> Este archivo es la fuente principal de contexto funcional para el desarrollo de la aplicación.
> Debe mantenerse legible para una persona desarrolladora y puede ser actualizado durante el proyecto cuando cambien requerimientos, arquitectura o decisiones funcionales importantes.

---

## 1. Propósito del proyecto

**Super Cocina del Valle** será una aplicación web para administrar la operación de una fonda, tomando como base el proyecto existente **Suerte Café**.

El objetivo es reutilizar al máximo la arquitectura, componentes, modelos, comportamientos y experiencia obtenida en Suerte Café, pero adaptándolos a una operación más compleja:

- aproximadamente 170 a 250 pedidos por día;
- seis días de operación por semana;
- atención a mesas;
- pedidos para recoger;
- pedidos para entrega;
- pedidos generados directamente por clientes desde una interfaz pública;
- menú fijo;
- menú diario rotativo;
- control de stock;
- impresión de comandas y tickets;
- asignación de empleados;
- propinas;
- caja;
- gastos;
- reportes operativos.

La prioridad del proyecto es:

1. simplicidad de operación;
2. bajo costo;
3. velocidad de captura;
4. facilidad de mantenimiento;
5. reutilización del proyecto Suerte Café;
6. claridad y trazabilidad de pedidos;
7. aislamiento entre el portal público y el entorno interno de empleados.

---

# 2. Estrategia general de arquitectura

No se crearán dos aplicaciones completamente independientes.

Se utilizará:

- un solo proyecto backend;
- una sola base de datos;
- un solo despliegue;
- módulos y permisos separados;
- dos superficies de interfaz claramente diferenciadas.

Estructura conceptual:

```text
Super Cocina del Valle
│
├── Sistema interno
│   ├── Login obligatorio
│   ├── Administrador
│   ├── Meseros
│   ├── Telefonistas / toma de pedidos
│   └── Repartidores
│
└── Portal público
    ├── Sin login
    ├── Cliente
    ├── Pedido para recoger
    └── Pedido para entrega
```

Ejemplo de rutas conceptuales:

```text
/app/                  Sistema interno
/app/mesas/            Flujo principal de meseros
/app/pedidos/          Flujo principal de telefonistas
/app/repartos/         Flujo de repartidores
/app/reportes/         Administración y reportes
/app/menu/             Administración de menú
/app/empleados/        Administración de empleados

/pedir/                Portal público
/pedir/menu/           Menú público
/pedir/carrito/        Carrito / construcción del pedido
/pedir/confirmacion/   Confirmación de recepción
```

El portal público no debe exponer navegación ni información del sistema interno.

---

# 3. Proyecto de referencia: Suerte Café

El proyecto existente **project_app_web_suerte_cafe** debe utilizarse como referencia técnica y funcional.

Se debe reutilizar, copiar o adaptar cuando resulte conveniente:

- Django;
- PostgreSQL;
- estructura general del proyecto;
- autenticación;
- perfiles;
- permisos;
- sidebar;
- topbar;
- temas/apariencia;
- pedidos;
- detalle de pedido;
- edición de pedido;
- productos;
- categorías;
- opciones configurables de productos;
- productos modificados;
- precios adicionales;
- envases;
- snapshots históricos;
- reportes base;
- manejo de imágenes;
- optimización de imágenes;
- paginación;
- validaciones;
- manejo de errores;
- seguridad del backend;
- variables de entorno;
- estructura de despliegue objetivo;
- estrategia de backups.

No debe copiarse código a ciegas.

Antes de reutilizar una parte del proyecto Suerte Café se debe revisar:

1. qué problema resuelve;
2. si aplica directamente a Super Cocina del Valle;
3. si debe adaptarse;
4. si existe lógica que ya no es válida.

## 3.1 Funcionalidad implementada en Suerte Café relevante para Super Cocina del Valle

### Vista de Cocina con Filtros de Barras

**Fecha de implementación**: 4 de septiembre de 2026

**Propósito**: Implementar una vista de cocina que permita a los baristas filtrar pedidos según la barra que operan, con capacidad de marcar el estado de cada barra independientemente.

**Contexto**: La cafetería Suerte Café tiene dividida la cocina en dos barras:
- **Barra fría**: Bebidas (frías, calientes, sodas, etc.)
- **Barra caliente**: Comida (hot dogs, waffles, postres, sandwiches, etc.)

**Características principales**:

1. **Tres modos de filtro**:
   - **Barra fría**: Muestra solo productos clasificados como "COLD" (bebidas)
   - **Barra caliente**: Muestra solo productos clasificados como "HOT" (comida)
   - **2 players**: Vista dividida en dos columnas mostrando ambas barras simultáneamente

2. **Estados independientes**:
   - Cada pedido tiene `cold_bar_status` y `hot_bar_status` independientes
   - El estado general del pedido solo se marca como COMPLETED cuando ambas barras están COMPLETED
   - Evita que una barra cierre accidentalmente todo el pedido

3. **Diseño de la interfaz**:
   - **Prioridad visual**: Producto, cantidad, personalizaciones, notas, tipo de pedido
   - **Información secundaria**: Nombre del cliente, mesa, total
   - **Botones grandes**: Filtros principales fáciles de usar en ambiente de cocina
   - **Auto-refresco**: Actualización cada 30 segundos
   - **Responsive**: Funciona en móviles y tablets

**Implementación técnica**:

- **Modelo Order**: Agregados campos `cold_bar_status` y `hot_bar_status`
- **Modelo Category**: Campo `preparation_station` (COLD/HOT)
- **Modelo Product**: Campo `preparation_station` opcional para sobrescribir la categoría
- **Modelo OrderItem**: Campo `preparation_station_snapshot` para preservar histórico
- **Vista kitchen_view**: Filtra y separa pedidos por barra
- **API update_bar_status**: Actualiza estado de cada barra independientemente
- **Método update_overall_status**: Actualiza estado general basado en barras

**Configuración de categorías**:
- Bebidas (frías y calientes) → Barra fría (COLD)
- Alimentos, Postres → Barra caliente (HOT)

**Relevancia para Super Cocina del Valle**:
- Super Cocina del Valle podría tener una división similar de cocina
- La lógica de estados independientes es aplicable a operaciones de cocina más complejas
- El concepto de clasificación por estación de preparación es escalable
- La vista dividida puede adaptarse para múltiples estaciones de trabajo
- Super Cocina del Valle maneja mayor volumen (170-250 pedidos/día vs volumen menor de Suerte Café)
- La funcionalidad de auto-refresco es crítica para alto volumen
- La clasificación por estaciones ayuda a distribuir carga de trabajo en cocina grande

**Consideraciones para adaptación**:
- Super Cocina del Valle podría necesitar más de dos barras/estaciones
- Los nombres de las estaciones pueden personalizarse según la operación
- La lógica de actualización de estados puede extenderse para N estaciones
- La vista "2 players" puede adaptarse a "N players" según necesidades
- Para alto volumen, considerar WebSockets en lugar de auto-refresco por intervalos
- Posible necesidad de vista de cocina específica para menú diario vs menú fijo
- Integración con sistema de impresión de comandas separadas por estación

---

# 4. Tipos de usuario

La aplicación tendrá los siguientes roles principales.

## 4.1 Administrador

Puede administrar toda la aplicación.

Funciones:

- visualizar todos los pedidos;
- crear y editar pedidos;
- reasignar mesas;
- administrar menú;
- administrar menú diario;
- administrar productos;
- administrar categorías;
- administrar paquetes;
- administrar stock;
- administrar zonas de entrega;
- administrar empleados;
- administrar mesas;
- registrar caja;
- registrar gastos;
- consultar reportes;
- consultar propinas;
- consultar entregas;
- configurar horarios;
- publicar/cerrar menú diario;
- imprimir documentos;
- realizar tareas administrativas.

---

## 4.2 Mesero

Su flujo principal son las mesas.

Pantalla principal:

```text
Mesas
```

Debe poder:

- visualizar sus mesas;
- abrir una mesa;
- crear una orden;
- agregar productos;
- modificar productos;
- agregar productos posteriormente a una cuenta abierta;
- consultar estado;
- imprimir comanda;
- imprimir cuenta;
- cerrar pedido;
- registrar método de pago;
- registrar propina;
- reasignar una mesa a otro mesero;
- visualizar pedidos para recoger o entrega en modo lectura cuando sea necesario.

No debe:

- administrar productos;
- administrar menú;
- administrar empleados;
- consultar reportes administrativos;
- modificar configuraciones sensibles.

---

## 4.3 Telefonista / empleado de toma de pedidos

Es el usuario que coordina pedidos externos.

Puede recibir pedidos:

- por llamada;
- por WhatsApp;
- en persona;
- desde el portal público.

Su pantalla principal será el panel de pedidos.

Debe poder:

- ver todos los pedidos externos;
- crear pedidos para recoger;
- crear pedidos para entrega;
- revisar pedidos públicos pendientes;
- confirmar pedidos públicos;
- contactar al cliente;
- revisar direcciones;
- asignar repartidor;
- consultar stock;
- modificar pedidos;
- crear o agregar productos a pedidos de mesa;
- seleccionar el mesero responsable de una mesa;
- imprimir comandas;
- imprimir tickets;
- visualizar estados de todos los pedidos relevantes.

Ejemplo de asignación:

```text
created_by = Juan (telefonista)
order_taker = Juan
assigned_waiter = Carlos
```

Aunque Juan capture la orden, la mesa pertenece a Carlos.

---

## 4.4 Repartidor

Su flujo principal serán únicamente pedidos para entrega.

Debe poder:

- visualizar pedidos disponibles para reparto;
- visualizar pedidos que tenga asignados;
- asignarse un pedido permitido;
- consultar dirección;
- consultar teléfono;
- consultar total;
- consultar método de pago;
- consultar si debe llevar terminal;
- consultar cambio necesario;
- marcar estados relacionados con reparto;
- registrar entrega;
- registrar propina cuando corresponda.

No debe acceder a:

- administración;
- reportes;
- configuración de menú;
- empleados;
- pedidos de mesas;
- información innecesaria de otras áreas.

---

## 4.5 Cliente público

No requiere cuenta.

No utiliza login.

Puede:

- consultar menú disponible;
- visualizar productos agotados;
- construir pedido;
- elegir recoger o entrega;
- seleccionar productos;
- seleccionar configuraciones;
- elegir piezas de productos cuando aplique;
- ver precios;
- proporcionar información de contacto;
- proporcionar dirección;
- seleccionar método de pago;
- indicar cambio requerido;
- enviar pedido.

No puede:

- visualizar otros pedidos;
- consultar empleados;
- consultar reportes;
- acceder al sistema interno;
- administrar productos;
- modificar pedidos internos.

---

# 5. Tipos de pedido

Se contemplan principalmente:

```text
TABLE
PICKUP
DELIVERY
WEB_PICKUP
WEB_DELIVERY
```

Puede simplificarse técnicamente si los pedidos públicos conservan un `source`.

Ejemplo recomendado:

```text
order_type:
- TABLE
- PICKUP
- DELIVERY

source:
- INTERNAL
- PUBLIC_WEB
```

---

# 6. Estados del pedido

Flujo definido:

```text
Pedido recibido
→ Pendiente de confirmar
→ Confirmado
→ En preparación
→ Listo
→ En reparto / Esperando recolección
→ Entregado
```

Para mesas se podrá adaptar el flujo omitiendo estados que no correspondan.

También debe existir:

```text
Cancelado
```

El control interno de estado es cíclico y conserva historial. Recoger termina en `Recogido`
y entrega termina en `Entregado`; desde cualquiera de esos estados puede iniciarse un nuevo
ciclo en `Pendiente de confirmar` sin borrar las transiciones anteriores.

La transición y permisos de estados deben definirse en backend.

---

# 7. Pedidos públicos

Cuando un cliente finaliza un pedido:

1. validar información;
2. validar disponibilidad;
3. validar stock;
4. crear pedido;
5. descontar stock;
6. guardar pedido con estado `Pendiente de confirmar`;
7. generar notificación interna;
8. mostrar confirmación al cliente.

El pedido debe aparecer inmediatamente:

- en la pantalla general de pedidos;
- en el centro de notificaciones;
- en los pendientes de confirmación.

Los pedidos públicos nunca deben depender de WhatsApp para existir.

---

# 8. Sistema interno de notificaciones

Se creará un centro de notificaciones interno.

Ejemplos:

```text
Nuevo pedido web #143
Cliente: Juan Pérez
Entrega
Total: $245
Dirección requiere validación
```

Debe existir:

- indicador visual;
- contador de pendientes;
- acceso rápido;
- enlace al pedido;
- estado leído/no leído;
- diferenciación de alertas.

Tipos potenciales:

```text
NEW_PUBLIC_ORDER
DELIVERY_ADDRESS_REVIEW
LOW_STOCK
OUT_OF_STOCK
ORDER_READY
ORDER_CANCELLED
```

Se puede agregar señal sonora opcional.

---

# 9. WhatsApp

WhatsApp se considera una integración adicional, no la fuente principal de notificación.

Arquitectura conceptual:

```text
NotificationService
│
├── InternalNotification
└── WhatsAppNotification
```

La integración automática con WhatsApp queda pendiente de decisión por costos y configuración.

La aplicación debe poder operar completamente aunque WhatsApp no se implemente.

---

# 10. Información del cliente

## Recoger

Datos:

- nombre;
- apellido obligatorio para identificar al cliente al recoger;
- teléfono.

## Entrega

Datos:

- nombre;
- teléfono;
- calle;
- número exterior;
- número interior;
- colonia;
- referencias;
- notas;
- método de pago;
- información de cambio cuando corresponda.

Los datos del cliente pueden reutilizarse posteriormente por teléfono o identificador normalizado, sin obligar a crear una cuenta.

---

# 11. Métodos de pago

La aplicación no tendrá pasarela de pago.
En la interfaz el método se llama `Terminal`; `CARD` queda únicamente como código interno
compatible con los registros existentes y no significa que la aplicación cobre en línea.

Para recoger no se solicita método de pago en el portal; el cliente lo define al llegar a la fonda.
Para entrega sí es obligatorio indicarlo: Terminal implica llevar el dispositivo físico, transferencia no
requiere preparación adicional y efectivo debe indicar billete/monto o pago exacto.

Debe registrar:

```text
CASH
CARD
TRANSFER
```

## Efectivo

Preguntar:

```text
¿Necesitas cambio?
```

Si sí:

```text
¿Con cuánto vas a pagar?
```

Guardar:

```text
payment_method
cash_received_expected
change_required
```

Ejemplo:

```text
Total: $327
Cliente paga con: $500
Cambio requerido: $173
```

Esta información debe ser visible para el repartidor.

## Terminal

Debe mostrarse al personal/repartidor:

```text
LLEVAR TERMINAL
```

## Transferencia

Se registra como método de pago.

También puede contener propina.

---

# 12. Propinas

La propina se registra dentro del pedido.

Reglas actuales:

```text
Mesa:
100% para el mesero responsable.

Entrega:
100% para el repartidor.
```

Registrar:

```text
tip_amount
```

y asociar la propina al empleado beneficiario correspondiente.

Los reportes deben poder calcular:

- propinas por mesero;
- propinas por repartidor;
- total de propinas;
- propinas por método de pago;
- propinas por fecha.

---

# 13. Mesas

Las mesas serán entidades reales.

Entidad conceptual:

```text
Table
- id
- name
- status
- assigned_waiter
```

Estados posibles:

```text
AVAILABLE
OCCUPIED
```

Una mesa puede tener una cuenta/pedido abierto.

Ejemplo:

```text
Mesa 3
09:15  2 chilaquiles
       2 cafés

09:37  +1 café
       +1 jugo

10:05  +1 hot cakes
```

Todo permanece dentro de la misma cuenta hasta cerrarse.

Meseros y administrador podrán reasignar mesa.

Primera implementación acordada:

- el estado Disponible/Ocupada se deriva de la existencia de una cuenta abierta;
- Administración crea y ordena visualmente las mesas;
- Mesero abre para sí mismo; Administrador o Telefonista pueden elegir al mesero responsable;
- PostgreSQL garantiza una sola cuenta abierta por mesa;
- la cuenta se cobra completa con efectivo, terminal o transferencia; no se divide el pago;
- efectivo permite pago exacto o monto recibido y calcula el cambio;
- la propina de mesa pertenece completamente al mesero responsable al momento del cierre;
- cerrar fotografía subtotal, propina, total, efectivo, cambio y responsables, y libera la mesa;
- una cuenta cerrada conserva su ticket y cobro en modo de solo lectura.
- efectivo muestra solamente billetes rápidos de $20, $50, $100, $200 y $500;
- tocar un billete selecciona Efectivo, valida que cubra total más propina y calcula cambio;
- propina de mesa ofrece montos rápidos de $5, $10, $15, $20, $25 y $30, además de captura manual;
- el panel de Mesas separa el mapa activo de un historial consultable de hoy y de la semana;
- cada Mesero ve sus propias cuentas históricas, mientras Administración y Telefonista ven todas.

Distribución visual vigente:

```text
M8   M7   M6   M5   M9
M1   M2   M3   M4
```

El mapa operativo de escritorio/tablet usa dos filas horizontales: M8, M7, M6, M5 y M9
arriba; M1, M2, M3 y M4 abajo. Debe mostrar las nueve sin scroll. Al tocar una
mesa disponible, el Mesero abre su cuenta; al tocar una ocupada continúa el ticket activo.
La interfaz cotidiana evita escritura y prioriza botones, categorías y selecciones.
Administrador y Telefonista ven botones con nombres de meseros activos para abrir y asignar
en un solo toque; el Mesero se asigna automáticamente al abrir.

La captura de mesa tiene modo Desayunos (07:00–12:59) y Comida (13:00–06:59). El modo se
elige automáticamente, pero cada usuario puede sobrescribirlo en su sesión desde mapa o
cuenta. Categorías definen orden y visibilidad independientes por modo; durante desayuno,
una categoría configurable revela los paquetes, mientras comida los prioriza arriba.

En cuentas de mesa, corrida y ejecutiva no preguntan tortillas ni frijoles. Se pueden
guardar con tiempos pendientes, quedan identificadas con texto en el ticket y se editan
tocando la partida. El cierre transaccional se bloquea mientras exista una comida incompleta.
Cada paquete conserva el menú diario original para poder terminar una cuenta abierta en una
fecha posterior sin sustituir sus opciones por las del nuevo día.

En Modo comida, `Comida por orden` se deriva del menú diario publicado: dos primeros
tiempos, dos segundos y tres guisados. Solo se venden los componentes configurados como
individuales y disponibles; el backend valida pertenencia al menú antes de agregarlos.
Los nombres `Comida corrida`, `Comida ejecutiva` y `Comida por orden` están reservados para
estos accesos dinámicos: las categorías persistentes homónimas no se muestran como catálogo
normal en Desayunos ni en Comida, evitando mezclar productos de menús anteriores.

La captura de consumos de mesa se implementa como punto de venta táctil:

- categorías y productos individuales mediante botones grandes;
- un toque registra inmediatamente una unidad; repetir producto incrementa la misma línea;
- ticket lateral con producto, cantidad, subtotal y total, sin paso de confirmación;
- agregar, aumentar, disminuir y quitar se realiza en segundo plano sin recargar la página;
- pestañas superiores de categorías muestran una sola lista de productos a la vez;
- Django conserva validación, bloqueo, cálculo y snapshots aunque JavaScript actualice la interfaz;
- paquetes corrida/ejecutiva usan su flujo guiado de tres tiempos y complementos.

Implementación posterior de paquetes en mesa:

- corrida y ejecutiva se abren desde botones destacados en el catálogo del mesero;
- un diálogo mantiene al usuario dentro de la misma cuenta mientras elige los tres tiempos;
- agua, tortillas, frijoles, pieza de pollo y refill se validan antes de agregar;
- configuraciones idénticas suman cantidad y configuraciones diferentes conservan líneas separadas;
- el ticket guarda snapshots completos y calcula con/sin agua más el cargo único de refill.

Reglas de anticipación y pieza:

- corrida y ejecutiva pueden solicitarse públicamente antes del horario de comida;
- antes de la 1:00 p. m. la interfaz avisa que se está agendando para servirse/recogerse desde esa hora, sin bloquear;
- pierna/muslo se muestra únicamente al elegir pollo y entonces la selección es obligatoria;
- estas reglas se validan tanto en interfaz como en backend.

---

# 14. Responsabilidades dentro del pedido

No utilizar un único campo `employee`.

Separar responsabilidades:

```text
created_by
order_taker
assigned_waiter
delivery_person
```

Esto permite rastrear:

- quién capturó;
- quién tomó la orden;
- quién atendió la mesa;
- quién realizó la entrega.

---

# 15. Menú fijo

Contiene productos que normalmente están disponibles de forma continua:

- desayunos;
- huevos;
- chilaquiles;
- enchiladas;
- sopes;
- tortas;
- sandwiches;
- hot cakes;
- productos de plancha;
- bebidas;
- otros.

Los productos pueden tener:

- categoría;
- precio;
- descripción;
- imagen;
- horarios;
- disponibilidad;
- stock opcional;
- configuraciones;
- modificadores;
- envase.

## 15.1 Periodos de servicio

La clasificación visual de un producto no determina por sí sola su horario.

Existirán al menos estos periodos, que pueden superponerse:

```text
DESAYUNO: 08:00 - 13:00
COMIDA:   12:30 - 17:00
```

Un mismo producto puede pertenecer a uno o varios periodos. Por ejemplo, `Huevos machacados` puede venderse durante desayuno y comida sin duplicar el producto.

Entre 12:30 y 13:00 podrán ofrecerse simultáneamente productos de desayuno y comida.

---

# 16. Menú diario

El administrador podrá crear un menú correspondiente a un día.

Ejemplo:

```text
Lunes 24 de agosto

Sopas
- Consomé
- Sopa de pasta

Segundo tiempo
- Arroz rojo
- Arroz blanco
- Espagueti

Guisados
- Mole de pollo
- Bistec en chile pasilla
- Tacos dorados
```

Debe poder:

- crear;
- editar;
- programar;
- publicar;
- cerrar;
- consultar históricos.

Solo un menú publicado debe mostrarse al cliente.

El menú diario también define el único sabor de agua disponible ese día. El sabor puede cambiar diariamente.

## 16.1 Estructura fija del menú diario

El menú diario siempre tiene tres tiempos con una cantidad fija de opciones:

```text
Primer tiempo:  2 opciones
Segundo tiempo: 2 opciones
Tercer tiempo:  3 opciones
Total:          7 componentes
```

### Primer tiempo

Siempre contiene exactamente:

```text
1. Consomé de pollo (opción fija)
2. Opción variable: sopa de pasta, lentejas, minestrone, crema u otra equivalente
```

### Segundo tiempo

Siempre se eligen exactamente dos opciones distintas de este catálogo:

```text
- Arroz rojo
- Arroz blanco
- Espagueti rojo
- Espagueti blanco
```

### Tercer tiempo

Siempre contiene exactamente tres guisados, uno por función:

```text
1. Un guisado de pollo
2. Un guisado de res
3. Un guisado variado
```

La interfaz debe presentar lugares explícitos para cada opción y validar esta estructura antes de publicar. No debe permitir una cantidad libre de componentes por tiempo.

---

# 17. Horarios

Debe poder configurarse disponibilidad por horarios.

Ejemplo:

```text
Desayunos:
08:00 - 12:30

Comida:
13:00 - 17:00
```

La disponibilidad de productos y secciones puede depender del horario.

---

# 18. Paquetes

El sistema debe soportar paquetes configurables.

## Comida corrida

```text
1 sopa
+ 1 segundo tiempo
+ 1 guisado
+ complementos
```

## Comida corrida con agua

```text
Comida corrida
+ bebida permitida
```

## Comida ejecutiva

```text
1 sopa
+ 1 segundo tiempo
+ 1 producto elegible de plancha
+ complementos
```

## Comida ejecutiva con agua

```text
Comida ejecutiva
+ bebida permitida
```

No todos los productos pueden formar parte de una comida ejecutiva.

Debe existir una propiedad o relación que determine los productos elegibles.

Ejemplo conceptual:

```text
eligible_for_executive_meal = true
```

## 18.1 Variantes con y sin agua

Comida corrida y comida ejecutiva tendrán variantes con agua y sin agua, con precios diferentes.

Para la variante con agua:

```text
Mesa:
- incluye 2 vasos;
- no se registra cada vaso servido;
- la interfaz muestra `2/2 vasos incluidos`;
- una casilla `Refill extra` agrega una única tarifa adicional a esa comida.

Recoger / entrega:
- incluye 1 vaso;
- no existen refills incluidos ni adicionales asociados al paquete.
```

El agua incluida corresponde al único sabor publicado para el día.

El refill se controla como una preferencia/cargo booleano de la partida del paquete (`con refill` / `sin refill`), no como un contador de vasos ni como múltiples eventos de servicio.

## 18.2 Complementos incluidos

Tortillas y frijoles son complementos sin costo adicional dentro de comida corrida y ejecutiva.

El empleado debe preguntar en cada pedido:

```text
¿Lleva tortillas? Sí / No
¿Lleva frijoles? Sí / No
```

Estas respuestas deben guardarse como datos estructurados y mostrarse claramente en comandas y pedidos externos; no deben depender únicamente de notas libres.

---

# 19. Venta por orden

Los componentes del menú también pueden venderse individualmente.

Ejemplos:

```text
Orden de sopa
Orden de arroz
Orden de guisado
Orden de producto de plancha
```

Si una combinación no cumple las reglas de un paquete, debe cobrarse como productos/órdenes individuales.

“Órdenes” es una forma de vender individualmente productos del catálogo o componentes del menú diario; no requiere duplicar el producto utilizado dentro de un paquete.

---

# 20. Productos configurables

Se reutilizará la lógica de Suerte Café.

Un producto puede tener grupos de opciones.

Ejemplos:

```text
Mole de pollo

Pieza:
○ Pierna
○ Muslo
```

Las configuraciones diferentes deben conservarse como partidas diferentes.

Los productos modificados deben indicarse visualmente.

Se conservarán snapshots históricos.

---

# 21. Stock

El stock debe poder aplicarse:

- al menú diario;
- a productos fijos;
- a variantes;
- a piezas específicas.

Ejemplo:

```text
Mole de pollo
├── Pierna: 40
└── Muslo: 40
```

El cliente debe seleccionar explícitamente la pieza.

## Descuento

El stock se descuenta cuando el pedido se confirma/envía, no al agregar al carrito.

Debe realizarse de manera segura para evitar vender inventario inexistente.

## Cancelación

Si un pedido es cancelado:

```text
devolver stock
```

## Umbrales

Cada elemento puede tener:

```text
stock
low_stock_threshold
critical_stock_threshold
```

Ejemplo:

```text
40 disponibles
10 = alerta baja
5 = alerta crítica
0 = agotado
```

## Agotado

Tanto clientes como empleados seguirán viendo el producto, pero marcado:

```text
AGOTADO
```

No se podrá agregar a nuevas órdenes.

---

# 22. Zonas de entrega

No utilizar Google Maps en la primera versión.

La lógica del negocio se basará en calles y rangos permitidos.

Ejemplo:

```text
DeliveryStreetRange

street
min_number
max_number
zone
active
```

Podrán existir:

```text
NORMAL
EXTENDED
```

El administrador podrá definir el modo de reparto del día.

Ejemplo:

```text
Zona activa: NORMAL
```

En días tranquilos:

```text
Zona activa: EXTENDED
```

---

# 23. Dirección fuera de rango

No se bloqueará automáticamente al cliente.

Si la dirección está fuera de zona:

```text
Tu dirección está fuera de nuestra zona habitual.
Puedes enviar el pedido.
Super Cocina del Valle confirmará si es posible realizar la entrega.
```

El pedido entra como:

```text
Pendiente de confirmar
requires_delivery_review = true
```

El sistema genera una notificación prioritaria para telefonista/admin.

El personal decide si acepta o rechaza el pedido y contacta al cliente.

---

# 24. Envases

Se reutilizará la lógica de Suerte Café.

Los envases tienen:

- nombre;
- precio;
- disponibilidad;
- orden.

Los pedidos para recoger y entrega pueden calcular envases automáticamente.

Los envases forman parte del total.

Los snapshots históricos deben conservarse.

---

# 25. Impresión térmica

Impresora actual:

```text
Marca: OFICHIDO
Modelo: POS-8360
Tipo: Thermal receipt printer
```

Solo existe una impresora inicialmente.

Nada debe imprimirse automáticamente.

Toda impresión requiere una acción explícita del usuario.

---

# 26. Tipos de impresión

## Documento 1 — Comanda de cocina

Debe mostrar principalmente:

- número de pedido;
- mesa / recoger / entrega;
- productos;
- cantidades;
- configuraciones;
- modificaciones;
- notas;
- hora.

Objetivo:

```text
Chef / cocina
```

## Documento 2 — Control / cobro

Debe mostrar:

- pedido;
- cliente;
- total;
- forma de pago;
- cambio;
- mesero/repartidor;
- información necesaria para caja.

## Documento 3 — Ticket para cliente

Opcional.

Se imprime cuando el cliente lo solicita.

---

# 27. Pedidos para recoger y entrega

Cuando se imprima un pedido externo normalmente deben generarse:

1. comanda;
2. control/cobro.

El ticket del cliente es opcional.

---

# 28. Caja

Debe existir registro diario de caja.

Entidad conceptual:

```text
DailyCashRegister
```

Debe guardar al menos:

```text
date
opening_cash
```

Posteriormente podrá participar en cálculos del corte diario.

---

# 29. Gastos

Registrar gastos del día.

Ejemplos:

- pan;
- tortillas;
- Bimbo;
- gas;
- refrescos;
- verduras;
- otros.

Debe existir catálogo reutilizable de conceptos frecuentes.

Entidad conceptual:

```text
ExpenseCategory
```

Y registros:

```text
Expense
- date
- category
- concept
- amount
- created_by
```

---

# 30. Reportes

Solo administradores.

Reportes previstos:

```text
Ventas
Pedidos
Productos
Propinas
Empleados
Repartos
Inventario
Gastos
Corte del día
```

Debe poder consultar al menos:

- ventas del día;
- pedidos por tipo;
- pedidos por estado;
- ventas por mesero;
- ventas por telefonista;
- entregas por repartidor;
- propina por mesero;
- propina por repartidor;
- total de propinas;
- productos más vendidos;
- guisados vendidos;
- stock inicial;
- stock vendido;
- stock restante;
- pedidos cancelados;
- ventas por método de pago;
- gastos;
- fondo inicial de caja.

---

# 31. Corte del día

Ejemplo conceptual:

```text
24 agosto 2026

Fondo inicial                $2,000
Ventas efectivo              $7,450
Ventas terminal              $5,320
Transferencias               $1,950

Gastos:
Pan                            $350
Tortillas                      $420
Bimbo                          $180

Propinas                     $1,240
```

La estructura final deberá definirse conforme avance el proyecto.

---

# 32. Seguridad

Los permisos deben validarse en backend.

Ocultar botones no sustituye autorización.

Debe impedirse que:

- clientes accedan a `/app/`;
- meseros accedan a administración;
- repartidores accedan a reportes;
- usuarios modifiquen pedidos que no tienen permitido modificar;
- endpoints internos sean consumidos sin autenticación.

Mantener:

- CSRF;
- cookies seguras en producción;
- HTTPS;
- validación de uploads;
- manejo seguro de variables de entorno;
- páginas de error;
- validación de permisos.

---

# 33. Arquitectura técnica objetivo inicial

Se busca conservar una arquitectura simple y económica.

Base prevista:

```text
Browser
   ↓
Cloudflare
   ↓
Amazon Lightsail
   ↓
Nginx
   ↓
Gunicorn
   ↓
Django
   ↓
PostgreSQL
```

Inicialmente Django y PostgreSQL pueden convivir en el mismo servidor si los recursos lo permiten.

---

# 34. Volumen esperado

```text
170 - 250 pedidos por día
6 días por semana
```

La aplicación debe ser eficiente, pero no requiere microservicios.

Priorizar:

- monolito modular;
- consultas optimizadas;
- índices adecuados;
- paginación;
- transacciones;
- manejo seguro de stock;
- bajo número de servicios externos.

---

# 35. Backups

Tomar como referencia la estrategia de Suerte Café.

Objetivo:

- `pg_dump`;
- exportación a Excel;
- respaldo de imágenes/media;
- compresión;
- copia fuera del servidor;
- política de retención.

El Excel es una copia legible de negocio.

No sustituye el dump técnico de PostgreSQL.

---

# 36. Reutilización vs desarrollo nuevo

## Reutilizar/adaptar de Suerte Café

- autenticación;
- perfiles;
- permisos;
- layout interno;
- temas;
- productos;
- categorías;
- opciones;
- envases;
- pedidos base;
- historial;
- snapshots;
- imágenes;
- reportes base;
- manejo de errores;
- PostgreSQL;
- Django;
- seguridad;
- backups;
- infraestructura objetivo.

## Desarrollo nuevo

- portal público;
- roles operativos nuevos;
- mesas como entidades;
- cuentas abiertas de mesa;
- pedidos web;
- estados extendidos;
- centro de notificaciones;
- menú diario;
- paquetes;
- elegibilidad para comida ejecutiva;
- stock;
- variantes de stock;
- alertas de stock;
- zonas de entrega;
- validación de rangos de calles;
- repartidores;
- responsabilidades múltiples del pedido;
- propinas;
- caja;
- gastos;
- corte diario;
- impresión térmica;
- templates de comanda;
- control/cobro;
- ticket cliente.

---

# 37. Principios de desarrollo

1. No sobrearquitecturar.
2. Reutilizar antes de reescribir.
3. No copiar código sin analizarlo.
4. Mantener responsabilidades claras.
5. Mantener el proyecto fácil de entender.
6. Evitar dependencias externas innecesarias.
7. Mantener bajo costo operativo.
8. Validar reglas críticas en backend.
9. Usar transacciones en operaciones sensibles.
10. Mantener historial de cambios relevantes.
11. No romper funcionalidades de Suerte Café al usarlo como referencia.
12. No asumir requerimientos no documentados.
13. Registrar decisiones importantes.

---

# 38. Estado del proyecto

## Fase 1 — Arquitectura

Estado:

```text
EN DEFINICIÓN / BASE FUNCIONAL DOCUMENTADA
```

## Fase 2 — Código

```text
PENDIENTE
```

## Fase 3 — Despliegue

```text
PENDIENTE
```

---

# 39. Decisiones pendientes

Actualmente quedan abiertas, entre otras:

- integración automática con WhatsApp;
- detalle final del cálculo/cierre de caja;
- permisos específicos de captura de gastos;
- permisos específicos de apertura/cierre de caja;
- compatibilidad técnica de la impresora OFICHIDO POS-8360;
- método técnico de impresión desde navegador/servidor;
- estructura final de URLs;
- estructura final de Django apps;
- estrategia definitiva de despliegue;
- estrategia definitiva de backups;
- detalles finales de reportes.

Estas decisiones pueden actualizarse conforme avance el desarrollo.

---

# 40. Regla de mantenimiento de este documento

Este archivo representa la visión funcional y técnica humana del proyecto.

Puede ser actualizado durante el desarrollo cuando exista:

- un nuevo requerimiento;
- una decisión funcional;
- un cambio de arquitectura;
- una eliminación de funcionalidad;
- una modificación importante de comportamiento.

No debe utilizarse como bitácora de cada pequeño cambio de código.

La bitácora operativa y el contexto de trabajo de Codex deben conservarse en `CODEX_CONTEXT.md`.

La navegación superior interna debe derivarse de la misma matriz de permisos que protege las vistas:

- Administrador: Mesas, Pedidos, Repartos, Reportes y Menú.
- Mesero: Mesas y Pedidos.
- Telefonista: Mesas, Pedidos y Repartos.
- Repartidor: Repartos.

No se muestran enlaces a módulos que el usuario no puede abrir. La navegación no sustituye
las validaciones backend; ambas consultan la misma configuración de roles.
La cabecera separa las acciones de sesión de los accesos operativos. Los módulos deben tener
contraste alto, estado activo inequívoco y conservar botones táctiles legibles en tablet.

La administración de Menú ofrece un organizador visual de categorías con cinco vistas:
orden general, Cliente en desayunos/comida y Mesas en desayunos/comida. Administración reordena mediante
arrastre y observa el resultado antes de guardar. Las categorías ocultas permanecen visibles
como configuración atenuada. Los accesos automáticos de Corrida y Ejecutiva permanecen al
inicio; Comida por orden usa la posición de su tarjeta configurable en Mesas · Comida. Las cinco
secuencias se validan y guardan juntas.
El cliente usa el panel Desayunos antes de las 12:30 y Comida desde las 12:30; cada panel
permite ocultar categorías sin afectar el otro modo ni la captura interna de Mesas.

## Decisión funcional: asignación de repartos

- Todo pedido a domicilio entra al panel de Repartos sin importar su estado operativo.
- Administrador, Telefonista y Repartidor pueden asignar o sustituir al repartidor responsable en cualquier momento.
- Cada entrega tiene un solo repartidor responsable actual y conserva quién y cuándo realizó la asignación más reciente.
- Los tres roles consultan las asignaciones actuales para poder coordinarlas y reasignarlas.
- Solo el responsable asignado, Administrador o Telefonista pueden marcar el pedido como Entregado.
- Los pedidos para recoger quedan completamente fuera de este módulo.

## Decisión funcional: armado automático de comidas en mesa

- El menú diario publicado es la fuente de las categorías operativas Comida corrida, Comida ejecutiva y Comida por orden en la captura de mesas.
- Comida corrida se reconoce únicamente al reunir un primer tiempo, un segundo tiempo y uno de los guisados publicados.
- Comida ejecutiva se reconoce únicamente al reunir un primer tiempo, un segundo tiempo y un producto de plancha marcado como elegible.
- Antes de completar los tres tiempos, cada selección permanece identificada como candidato de paquete, separada de las órdenes individuales.
- Al completar la combinación, las tres unidades individuales se sustituyen por una sola partida de paquete y se aplica el precio del paquete sin agua.
- En Comida corrida y Comida por orden, elegir pollo abre una selección rápida obligatoria de Pierna o Muslo.
- La pieza acompaña a la orden o al paquete automático; el formulario completo conserva la misma selección para el flujo alternativo y la edición.
- El agua y refill pueden ajustarse posteriormente desde el detalle de la partida.
- Las selecciones hechas dentro de Comida por orden nunca se convierten en paquete.
- Una cuenta no puede cerrarse con candidatos incompletos: el mesero debe completar el paquete o eliminarlos.
- Un producto de plancha elegible puede participar en Ejecutiva sin estar habilitado para venta individual; para aparecer también en Plancha debe permitir venta por orden.
- Todo el entorno interno `/app/mesas/` ignora los periodos horarios para permitir al personal continuar generando comandas.
- El horario de cierre de las 17:00 aplica únicamente al flujo público `/pedir/menu/`; disponibilidad activa y permiso de venta individual siguen aplicando donde corresponda.
- En Mesas, Comida por orden contiene exclusivamente los siete componentes del menú publicado y, si fue configurada, una Orden de frijoles tipo Complemento.
- Elegir desde Comida por orden siempre crea una orden independiente; elegir los tiempos desde Comida corrida crea candidatos que deben completar corrida o ejecutiva.
- La orden de frijoles nunca cuenta como tiempo ni puede ayudar a formar un paquete.
- Los formularios directos de Comida corrida y Comida ejecutiva siguen disponibles como método alternativo.

## Decisión funcional: ingredientes y personalización

- Cada producto puede tener grupos de ingredientes u opciones reutilizables mediante copia.
- Un grupo admite elección única o múltiple y puede exigir conservar alguna selección.
- Cada opción indica si forma parte de la preparación estándar, si está disponible y su cargo adicional.
- Copiar/pegar un grupo crea una copia independiente para que modificar un producto no altere otros.
- Producto, grupos y todas sus opciones se crean o editan desde una sola pantalla y se guardan como una operación transaccional.
- El administrador puede agregar filas, reordenarlas y pegar grupos existentes sin navegar entre formularios por ingrediente.
- La personalización debe estar disponible tanto en el portal público como en la captura de Mesas.
- Quitar un ingrediente estándar, agregar una alternativa o cambiar una selección marca la partida como `Modificado`.
- El ticket y la orden guardarán snapshots y diferencias legibles para conservar el historial aunque cambie la receta.
- Dos unidades del mismo producto con configuraciones distintas deben permanecer en partidas separadas.
- Portal público y Mesas comparten la misma validación, cálculo de cargos y selector visual.
- Las opciones pueden compartir un par de sustitución: solo una alternativa del par permanece seleccionada y el cambio se describe como sustitución.
- Los grupos son familias reutilizables administradas desde `/app/menu/ingredientes/`; una familia puede asociarse a múltiples productos y sus cambios se propagan a todos.
- En catálogos de Mesas y cliente, `+`/`−` administran la preparación estándar y `Personalizar` genera una partida separada identificada por su firma de opciones.
- Una personalización admite comentario opcional; se muestra como `Producto (comentario)` y separa partidas aunque sus ingredientes coincidan.
- Las cuentas de mesa pueden registrar nombre opcional del cliente; el historial filtra por cliente y mesa, mientras el catálogo operativo busca productos transversalmente por nombre.
- La receta estándar aparece preseleccionada y no lleva etiqueta; cualquier diferencia muestra `Modificado`.
- Las diferencias de preparación se expresan como `Sin <ingrediente>` y `Agregar <opción>`.
- El carrito y el ticket agrupan solo producto + configuración idénticos y fotografían la selección al confirmar.
- En la captura automática de paquetes, sus tres tiempos permanecen estándar hasta diseñar personalización específica del paquete.
# Operación de meseros en tablet compartida

La tablet puede permanecer habilitada para cambio rápido entre perfiles de Mesero. Cada persona usa un PIN propio y la cabecera muestra permanentemente el operador activo. El cambio sustituye la autenticación real, no una identidad visual simulada. Administradores y telefonistas continúan usando el inicio de sesión normal.

La responsabilidad de una mesa y la autoría de un movimiento son conceptos distintos: el responsable conserva la propina salvo reasignación explícita, mientras la bitácora registra apertura, productos normales o modificados, cantidades, eliminaciones, paquetes, cliente, reasignación y cierre con el usuario que actuó.
# Panel de telefonistas y mostrador

Los pedidos internos y los pedidos públicos pueden reabrirse por folio, cliente o teléfono. El encabezado separa recoger y entrega, registra hora prometida y exige pago en ambos casos. El ticket persistente permite agregar productos después de una llamada o cuando el cliente llega, utilizando el mismo sistema de recetas, comentarios y paquetes.
### Captura para telefonistas

El editor interno conserva el patrón POS de mesas: menú y categorías a la izquierda, ticket y acciones a la derecha. La modalidad puede cambiarse durante la captura. Los datos del cliente, domicilio, forma de pago y notas se guardan como una unidad; en efectivo se muestran denominaciones rápidas y en terminal/transferencia se oculta el bloque de cambio. Los componentes de `Comida por orden` proceden del menú publicado del día.

El ticket permanece visible a la derecha mientras el telefonista recorre el formulario. Guardar un borrador permite datos parciales; al cerrar se validan los requisitos completos de entrega, cliente y pago.

La captura usa divulgación progresiva: los datos del cliente y domicilio se abren desde un botón de la barra operativa. Modalidad y pago permanecen como decisiones visibles; las denominaciones sólo aparecen con Efectivo. El ticket pertenece a una columna reservada y utiliza `sticky`, nunca `fixed`, para evitar cubrir el catálogo.

Corrida y ejecutiva para telefonistas se construyen por unidades de tiempos, sin campo Cantidad. Cada clic llena el primer grupo que carece de ese tiempo; al reunir primero, segundo y tercero, el sistema sustituye los candidatos por un paquete. Los grupos incompletos bloquean el cierre. Las preferencias de agua, tortillas, frijoles y comentario corresponden al siguiente paquete que se complete.

Datos internos: Recoger requiere nombre y fecha/hora de entrega; Entrega requiere además calle y número exterior. La fecha/hora se precarga desde la apertura del ticket y puede modificarse. Teléfono, interior, colonia, referencias y notas son opcionales; Entrega propone `del valle centro` como colonia.

El panel de cliente se autoguarda mientras se escribe y sus botones inferiores sólo lo retraen. Al fallar el cierre, la captura permanece abierta, enumera causas y lleva al primer campo inválido. Los paquetes pueden editar agua, tortillas, frijoles y comentario desde el ticket. Elegir el agua del día desde Bebidas frías actualiza el primer paquete sin agua antes de crear una bebida independiente.

En el catálogo interno, tocar la imagen equivale a pulsar `+`. La edición concurrente de extras bloquea primero la partida y consulta después el paquete nullable para respetar las restricciones `FOR UPDATE` de PostgreSQL.
### Cierre guiado de captura interna

Al cerrar un pedido de telefonista, cualquier dato obligatorio pendiente debe mostrarse en un resumen accionable. La interfaz abre automáticamente los datos del cliente y lleva el foco al primer campo inválido; el cierre nunca debe fallar sin explicar la causa.

`Guardar sin cerrar` conserva la captura como borrador y regresa al listado. `Cerrar captura` exige siempre una forma de pago, incluso para pedidos que serán recogidos en la fonda.

Los pedidos para Recoger usan `Mostrador` como cliente predeterminado. Si se conoce el nombre real, al entrar al campo el valor completo queda seleccionado para sustituirlo sin borrado manual.

### Programación y estados de pedidos

- Una hora o más entre apertura y entrega solicitada clasifica el pedido como `Programado`.
- Menos de una hora entra directamente en `En preparación`.
- Recoger: `Programado (si aplica) → En preparación → Listo → Recogido`.
- Domicilio: `Programado (si aplica) → En preparación → Listo → En reparto → Entregado`.
- La clasificación horaria se conserva separada del avance operativo.
- `/app/pedidos/` funciona como tablero: fila clicable al detalle, resumen breve del ticket, destino y transición rápida. Recoger y domicilio usan fondos distintos; el estado se distingue mediante una etiqueta de color independiente.
- Las transiciones rápidas son asíncronas para conservar el scroll. Estado y modalidad aplican el filtro al cambiar; la búsqueda utiliza una pausa breve antes de consultar. El tablero vuelve a consultar sus filtros cada siete segundos y sustituye exclusivamente las filas cuando cambiaron; espera si existe una interacción o guardado activo.
- Recoger puede abandonar captura sin pago, pero necesita registrarlo antes de `Recogido`; entrega lo requiere desde el cierre. Los errores de transición se muestran dentro de la misma fila.
- Los errores accionables enlazan a su resolución. Repartos reúne todas las entregas, permite filtros operativos y asignación/reasignación con botones asíncronos por repartidor.
- La presentación de Repartos es una lista horizontal; tanto asignación como avance de estado actualizan únicamente la fila para no perder la posición de trabajo.
- La propina de entrega cobrada por Terminal/Transferencia se almacena fuera del consumo y queda vinculada al repartidor asignado y al usuario que la editó. Reasignar transfiere el beneficiario. El ticket interno mantiene siempre visibles total y cierre mientras desplaza únicamente sus partidas.
- Capturar propina no requiere confirmación adicional: botones guardan inmediatamente y el monto libre después de una pausa. El editor del telefonista muestra el bloque sólo en Entrega con Terminal/Transferencia.

### Formato de folio

El folio presentado al personal y al cliente usa `DDMMNNN`: día, mes y consecutivo diario de tres posiciones. Por ejemplo, `0109001` identifica el primer pedido del 1 de septiembre. La numeración reinicia cada día y el buscador admite este formato compuesto.

### Agenda interna de clientes

Telefonistas y administradores cuentan con una agenda separada de los pedidos públicos. Una ficha conserva nombre, teléfono, indicaciones generales y múltiples domicilios con referencias. Una entrega interna completa sincroniza automáticamente su ficha y mantiene enlaces desde el pedido para que los siguientes autoguardados actualicen el mismo domicilio. Desde el capturador puede buscarse por nombre, teléfono o calle y rellenar todos los campos seleccionando una dirección.

El alta manual presenta en una sola pantalla la ficha y un domicilio inicial opcional. Si el domicilio queda vacío se crea únicamente el cliente; si se captura parcialmente, se requieren calle y número exterior antes de guardar ambos registros juntos.

La eliminación de clientes pertenece exclusivamente a Administrador y requiere confirmación. Una ficha con cualquier historial de adeudos no puede eliminarse, incluso cuando el registro financiero ya esté pagado o condonado. Al eliminar una ficha permitida desaparecen sus domicilios, mientras los pedidos históricos permanecen y simplemente dejan de apuntar a la agenda.

En el capturador, el propio campo Nombre del cliente consulta la agenda. Para Entrega despliega los domicilios y completa todos los datos; para Recoger muestra una selección por contacto, completa solamente nombre y teléfono y conserva la ficha vinculada sin domicilio. Un teléfono repetido se anuncia antes de continuar, identifica al propietario y ofrece revisar o reutilizar su ficha; el formulario de agenda también impide duplicarlo desde servidor. El listado operativo distingue consumo, propina y total final para entregas con propina.

Las coincidencias de nombre se ocultan al abandonar el campo. La protección telefónica también se ejecuta durante el autoguardado: si una ficha provisional recibe un número perteneciente a otro contacto, no modifica la agenda y devuelve el contacto correcto para que el operador lo seleccione.

El ticket de captura interna ofrece una nota general y una nota editable por cada partida. Ambas se actualizan sin eliminar productos y se destinan a la futura comanda de cocina. En modo comida se conservan simultáneamente los lanzadores grandes de Corrida/Ejecutiva y las categorías para armado automático por tiempos.

Los tickets laterales de Mesas y Telefonistas pueden tomar el foco ampliando su columna al tocar una zona no interactiva. Un fondo oscuro bloquea el resto de la aplicación mientras el ticket está enfocado: tocar fuera sólo restaura la proporción, sin ejecutar el control que quedó detrás. Un segundo toque en el fondo blanco del ticket o Escape también cierra el enfoque. Los botones y campos internos siguen siendo utilizables y quedan excluidos del disparador.

### Panel operativo de Caja

`/app/caja/` concentra para Administración los pedidos activos, con prioridad visual para entrega a domicilio. Cada fila permite reconocer folio, cliente, teléfono, domicilio y resumen, asignar al repartidor y registrar Efectivo, Terminal o Transferencia sin recargar. En efectivo, Caja registra el billete o pago exacto y confirma en un paso separado la entrega física del cambio al repartidor; esa constancia guarda usuario y hora, y se invalida si cambia el pago.

El listado de Caja se sincroniza automáticamente cada siete segundos. Sólo reemplaza las filas cuando detecta cambios y conserva el scroll; mientras el operador escribe o guarda una acción, la sincronización espera para no interrumpirlo.

Caja posee un cierre de revisión independiente del estado operativo: `cashier_released_at/by` retira de su bandeja un pedido ya verificado sin marcarlo como entregado ni afectar Cocina/Reparto. Una entrega requiere forma de pago y repartidor; el control de devolución de cambio al final del día es independiente y no bloquea el despacho. Al liberar se ofrece durante tres segundos `Seguir orden` para recuperar la fila; el billete vigente se resalta visualmente.

`/app/caja/cambios/` concentra las entregas en efectivo liberadas que sí generaron cambio. Por defecto muestra lo pendiente del día, permite filtrar por fechas, repartidor o conciliados, presenta totales por repartidor y registra el usuario y la hora al confirmar una devolución. Pago exacto queda fuera porque no genera un monto por conciliar.

Confirmar la devolución culmina también el pedido como `Entregado` mediante la máquina de estados, conservando las transiciones en el historial. El listado `/app/pedidos/` separa mediante el filtro `Mostrar` los pedidos activos —excluyendo Entregados, Recogidos y Cancelados—, los finalizados `Entregado/Recogido` y el conjunto completo.

Los tres paneles de Caja ofrecen navegación directa entre Caja, Cambios pendientes y Reporte de propinas. Las filas operativas mantienen azul para domicilio y naranja para recoger, con variantes más intensas cuando el horario es programado. En Caja, tocar una zona libre de la fila abre el pedido; botones, enlaces y campos quedan excluidos para conservar sus acciones rápidas.

La condición programada se refuerza mediante fondo, borde y una etiqueta con fecha/hora, sin depender de una diferencia cromática sutil. La columna completa de Cobro se excluye del acceso por fila. El monto personalizado de efectivo reduce su debounce a 250 ms y comunica de inmediato que está actualizando.

El reporte `/app/caja/propinas/`, también exclusivo de Administración, reúne las propinas cerradas de mesa y las registradas para reparto. Permite filtrar por fechas, Mesero/Repartidor, persona y método. Efectivo permanece visible como información pero no forma parte del total administrado, que sólo suma Terminal y Transferencia. El resultado ofrece totales globales, desglose por empleado y movimientos individuales.

Cada movimiento es seleccionable y consulta su ticket sólo al solicitarlo. El detalle se presenta como un panel modal que bloquea el fondo, conserva filtros y posición del reporte, y reúne cliente, responsable, destino, pago, propina, productos y notas. Puede cerrarse desde su botón, con Escape o tocando fuera.

El panel de Caja también permite avanzar el estado operativo usando exactamente la misma máquina de estados e historial que el listado de Pedidos. Cada fila presenta únicamente el siguiente paso válido y lo actualiza sin recarga; las reglas centrales siguen exigiendo, por ejemplo, un repartidor antes de iniciar reparto y una forma de pago antes de completar una recolección. En el listado general, las entregas identifican junto al domicilio al repartidor asignado o indican claramente que continúa sin asignar.

Para entregas cobradas con Terminal o Transferencia, la misma columna de Cobro ofrece propinas rápidas de `$0`, `$5`, `$10`, `$15`, `$20`, `$25` y `$30`, además de monto libre. Todo se guarda automáticamente en el registro compartido con Repartos y el reporte de propinas. Cambiar a Efectivo oculta el control porque esa propina no es administrada por el negocio.

En la captura interna, los lanzadores manuales de Comida corrida y Comida ejecutiva abren un selector visual con fotografía para primer tiempo, segundo tiempo y plato principal. La Corrida utiliza exclusivamente las opciones del menú diario publicado. La Ejecutiva conserva esos dos primeros tiempos y las opciones de plancha habilitadas, e incorpora una búsqueda local por nombre dentro del modal para localizar productos con rapidez.

En pantallas de operación amplias, los tres tiempos se distribuyen horizontalmente y usan tarjetas compactas para evitar desplazamiento en un menú diario normal. Agua, tortillas y frijoles se resuelven en una sola fila mediante controles grandes: Agua alterna Sí/No y tortillas/frijoles presentan ambos botones explícitos. Cada confirmación representa una comida, por lo que la cantidad permanece internamente fija en uno.

La elección Pierna/Muslo pertenece únicamente al guisado de pollo de la Comida corrida: permanece oculta hasta seleccionar ese producto y se limpia al cambiar a res o guisado variado. Comida ejecutiva utiliza plancha y nunca presenta una pieza de pollo. Los controles Sí/No se dibujan como botones completos aunque internamente preservan radios accesibles y la validación del servidor.

### Privacidad operativa de Repartos

El perfil Repartidor sólo consulta entregas todavía sin asignar y aquellas asignadas a su propio usuario. Puede tomar una entrega exclusivamente mediante autoasignación; no puede elegir a otro repartidor ni apropiarse de una entrega que ya tenga responsable. Administrador mantiene la asignación y reasignación completa, mientras Telefonista y Mesero no poseen esa acción. Estas reglas viven también en el servidor y no dependen de que un botón esté oculto.

Las propinas asignadas a una entrega propia pueden capturarse por el Repartidor mientras el pedido esté operativo, pero quedan bloqueadas para ese perfil después de Entregado o Recogido. El filtro de estados admite selección múltiple; no marcar ninguno equivale a consultar todos los estados permitidos para el usuario.

En una captura interna pagada en Efectivo, tanto para Entrega como para Recoger, la denominación es opcional al cerrar y enviar al listado. Si todavía no se conoce, `cash_tendered` permanece vacío y Caja/Repartos muestran `Monto por definir`; esto es distinto de Pago exacto. Si el operador sí selecciona billete, monto libre o exacto, se aplican las reglas y el cálculo de cambio habituales.

Liberar desde Caja funciona además como confirmación operativa acumulada. Un pedido para recoger recorre las transiciones pendientes hasta `Recogido`; una entrega a domicilio lo hace hasta `En reparto`. Se invoca la misma máquina de estados para registrar cada paso intermedio, usuario y hora. La operación es atómica: si falta pago, repartidor u otra condición, no avanza estados ni libera la fila.

En Repartos, el perfil Repartidor tiene una única transición: `En reparto → Entregado`, y sólo sobre un pedido asignado a su cuenta. No puede iniciar el reparto ni reiniciar ciclos; esas etapas permanecen en los perfiles internos autorizados. El detalle `/app/pedidos/<id>/` actualiza las transiciones y añade el nuevo renglón del historial mediante AJAX, conservando la posición vertical de la página.

Al alcanzar `En reparto`, el registro pasa a sólo lectura para cualquier perfil que no sea Administrador. El bloqueo se valida en cada endpoint de captura y también se refleja ocultando controles de productos, notas, datos del cliente, domicilio, pago, propina, extras y asignación. Telefonista sólo conserva la transición `En reparto → Entregado`; `Iniciar nuevo ciclo` es una operación exclusiva de Administrador.

La propina constituye una excepción acotada: durante `En reparto`, solamente el Repartidor asignado puede registrarla o corregirla; `Entregado` cierra ese permiso. Esto no habilita ninguna otra parte del pedido. Telefonista no captura propina al seleccionar Terminal porque aún no existe un importe confirmado; Transferencia sí puede conservar captura anticipada.

### Comandas imprimibles de 80 mm

Mesas y Pedidos internos ofrecen el mismo par de documentos: `Comanda cocina` y `Ticket de cobro`. Sólo Administrador, Mesero y Telefonista pueden abrirlos. Ninguna vista imprime automáticamente; el operador revisa la vista previa y pulsa el botón que abre el diálogo del navegador y Windows para la impresora térmica OFICHIDO POS-8360 conectada por USB.

La comanda de cocina comienza con una selección explícita de partidas. Cada renglón permite elegir una cantidad entre uno y la cantidad existente en el ticket, sin modificar el pedido original. De esta forma una segunda comanda puede incluir únicamente productos recién agregados o una fracción de una partida. La impresión enfatiza cantidad, nombre, componentes del paquete, modificaciones y comentarios; cliente, responsable, precios y total aparecen con jerarquía secundaria.

El ticket de cobro no admite selección parcial y siempre reconstruye todas las partidas. Para mesa destaca cliente/mesa, importes, pago, propina y total. Para recoger o entrega destaca además modalidad, teléfono, horario, dirección, referencias, necesidad de terminal, efectivo recibido y cambio. Ambos documentos usan CSS específico para papel de 80 mm y permanecen independientes de la futura integración directa con el controlador USB.

La presentación toma como guía las muestras operativas del negocio. Cocina encabeza con `Super Cocina Del Valle`, folio y modalidad (`A DOMICILIO`, `RECOGER` o `MESAS`), coloca cliente/dirección/mesero antes de las partidas y une el comentario al producto entre paréntesis. Cobro mantiene productos en dos columnas compactas y aumenta la jerarquía de cliente, domicilio, total y método. Los separadores de partidas son guiones horizontales rectos; nota general y productos comentados usan un marco de pequeños trazos diagonales, sin etiquetas adicionales, por lo que ambas señales se distinguen sin grandes manchas de tinta. En cobro de Mesa, tanto la etiqueta como el número se presentan sin negritas. En cobro de Recoger y Domicilio se incluyen la nota general y el texto de cada comentario de producto, sin prefijo, con tipografía secundaria.

La impresión de cocina dispone de dos recorridos explícitos. `Imprimir cocina` genera inmediatamente la vista previa con todas las partidas y cantidades. `Imprimir cocina modificado` conduce primero al selector, donde el operador decide qué partidas y cuántas unidades incluir sin alterar el ticket original. El ticket de cobro permanece siempre completo.

### Conciliación de terminales

`/app/caja/terminales/` digitaliza el registro manual de Clover y Mercado Pago. Por cada fecha existe un corte independiente por proveedor. Sus movimientos conservan total cobrado, propina, consumo calculado como `total − propina`, referencia visible de la terminal, vínculo opcional a pedido/mesa y la persona seleccionada como acreedora. Una propina mayor a cero exige beneficiario; el nombre mostrado por Clover permanece sólo como referencia y nunca asigna dinero automáticamente.

El mismo panel incluye un corte independiente de `Transferencias`. Clover y Mercado Pago sólo ofrecen como vínculos entregas a domicilio y cuentas de mesa cuyo pago sea Terminal; Transferencias ofrece exclusivamente entregas a domicilio pagadas por Transferencia. Los pedidos de tipo Recoger se excluyen de todos los selectores. Las cifras físicas y esperadas se concilian por separado: Clover+Mercado Pago contra Terminal, y Transferencias contra Transferencia.

Seleccionar un vínculo autocompleta el total cobrado, la propina y la persona beneficiaria. Para una entrega se toma primero `delivery_tip_recipient` y después el repartidor asignado; para una mesa se toma primero `tip_recipient` y después el mesero responsable. Caja puede editar cualquiera de esos valores tras vincularlo.

`Conciliación` funciona como una cuarta pestaña de sólo lectura. Agrupa por beneficiario la propina capturada en Clover, Mercado Pago y Transferencias, mostrando los tres subtotales, total por persona y total general. Para evitar fallos intermitentes, el cliente conserva una opción seleccionada hasta que el servidor confirma el guardado; una respuesta fallida no elimina prematuramente el candidato del resto de la interfaz.

La navegación Clover/Mercado Pago/Transferencias/Conciliación vive únicamente en las cuatro pestañas superiores. Los filtros visibles se limitan a Fecha y Persona; un valor oculto conserva la pestaña activa cuando cualquiera de esos filtros se aplica automáticamente.

### Cuentas por cobrar

`/app/caja/adeudos/` separa el cobro pendiente del flujo operativo: el pedido permanece `Entregado` o `Recogido`, mientras un `CustomerDebt` registra cliente de agenda, pedido, importe original, abonado, saldo y estado. Un pedido sólo puede generar un adeudo. Los estados son Pendiente, Pago parcial, Pagado y Condonado.

Cada abono, condonación o reapertura genera un `CustomerDebtMovement` con importe, método, nota, administrador y fecha. Administrador posee todas las mutaciones; Telefonista recibe lectura para consultar antes de atender. Caja incorpora un alta rápida por folio y la agenda muestra el historial del cliente. Al seleccionar un cliente con saldo en la captura, una advertencia persistente muestra total, número de pedidos y un enlace directo al panel filtrado.

Para la conciliación diaria, el importe esperado de Terminal o Transferencia se reconoce cuando la operación realmente concluyó: suma mesas cerradas, pedidos recogidos o entregados y abonos de adeudos cobrados durante la fecha seleccionada. Los pedidos activos, cancelados y aquellos convertidos en adeudo se excluyen del cobro original; el abono se incorpora en la fecha y mediante el método con que efectivamente se recibió. La posibilidad de vincular un renglón sigue reglas operativas más estrechas y no determina qué ingresos forman parte del total esperado.

El ticket de captura de Pedidos comparte el patrón responsivo de Mesas: columna proporcional, partidas con la misma estructura visual y desplazamiento de la tarjeta completa cuando rebasa el alto disponible. De esta forma los controles finales no quedan aislados de la lectura del ticket y en dispositivos estrechos el contenido se integra al flujo vertical sin un scroll interno forzado.

### Cargos e indicaciones de envases

Los envases se modelan como productos internos mediante `Product.packaging_kind`: paquete de envases, envase individual o cliente con recipientes propios. Pedidos mantiene una barra rápida independiente del horario y Mesas los agrupa dentro de la categoría `Envases`. Los formularios manuales para armar Corrida o Ejecutiva en ambos módulos permiten elegir cada tipo mediante `− cantidad +`; al confirmar, paquete y cargos se guardan atómicamente como partidas separadas. Cada envase participa naturalmente en total, impresión e historial y su cantidad puede corregirse desde el ticket. Nunca se muestran ni se aceptan desde el menú público. El catálogo inicial evita inventar tarifas: los cargos de paquete y tamaños nacen desactivados hasta que Administración capture su precio, mientras `Cliente trae recipientes` queda disponible con costo cero.

El selector manual de Corrida/Ejecutiva de Mesas comparte con Pedidos la presentación fotográfica en tres columnas. La estandarización es visual, no elimina reglas del flujo de mesa: permite guardar tiempos pendientes, conserva el refill y mantiene oculta la pieza de pollo hasta elegir el guisado correspondiente. Su formulario usa una sola columna estructural para no comprimir los tiempos; debajo muestra Envases como bloque independiente con imagen, precio y contador en ambos paquetes.

La captura se autoguarda: al completar una fila aparece otra vacía y las ediciones posteriores actualizan el mismo movimiento. Un corte cerrado bloquea edición y eliminación, registra usuario/hora y puede reabrirse para corregirlo. Se puede consultar por fecha, proveedor y persona, además de navegar directamente a Caja, Propinas y Cambios pendientes.

Los movimientos de conciliación no forman una segunda fuente contable. La interfaz muestra subtotales de Clover y Mercado Pago, pero compara la suma física de ambos contra todas las mesas y pedidos de esa fecha marcados como Terminal. Esto es necesario porque las ventas existentes conocen el método `Terminal`, pero no el proveedor físico. La propina se compara también por mesero o repartidor; coincidencias se muestran en verde y disparidades en rojo con sus importes.

Cada pedido o cuenta de mesa puede vincularse una sola vez, protegido tanto por la interfaz como por restricciones de base de datos. Al elegir el vínculo, total y propina se rellenan con el ticket original y luego permanecen editables para corregirlos contra la lectura real de Clover/Mercado Pago. Una opción utilizada deja de aparecer en otras filas y vuelve a habilitarse si se elimina o cambia su movimiento.

Administrador puede originar un adeudo directamente desde una fila finalizada o `En reparto` de `Pedidos` o `Cambios pendientes`. Esta última pantalla conserva como vista inicial los repartos en efectivo con cambio, pero permite ampliar por tipo, estado y forma de pago, incluyendo Terminal y Transferencia. Reportar `No pagó` desde `En reparto` completa primero la entrega mediante la máquina de estados y crea el adeudo en la misma transacción. Cuando el pedido ya está asociado, la acción se reemplaza por un enlace a su adeudo.

La unicidad abarca ambos proveedores: un ticket conciliado en Clover no puede reaparecer ni guardarse en Mercado Pago, y viceversa. Para mantener fluida la captura, un movimiento con propina puede vincularse antes de elegir beneficiario; queda temporalmente como `Sin asignar` y el toque posterior sobre un mesero/repartidor autoguarda esa asignación en la misma fila.

### Portal público visual y ticket en vivo

`/pedir/menu/` utiliza la modalidad guardada en sesión, presentada como dos botones grandes, y decide automáticamente la interfaz por hora. Desayuno ocupa el primer bloque hasta las 12:30 y muestra debajo la comida que puede adelantarse para después de la 1 p. m.; desde las 12:31 se priorizan en dos columnas los accesos a Corrida/Ejecutiva y una carta visual del menú diario. Las categorías se recorren con pestañas horizontales y las tarjetas agregan una unidad al tocar su fotografía.

El carrito se representa como ticket lateral en vivo desde la primera partida. Todas sus mutaciones —cantidad, eliminación, complementos, nota por partida y nota general— actualizan la sesión mediante JSON sin abandonar el menú. El ticket puede enfocarse y contraerse como los tickets internos; la nota general se precarga después en el checkout y las notas individuales se conservan en las partidas creadas.
