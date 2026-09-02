# NOTA TEMPORAL PARA APRENDIZAJE:
# Esta lista es la fuente única de los accesos internos. La barra y el panel consultan las
# mismas claves contra `SECTION_ROLE_MATRIX`, así nunca muestran un módulo sin permiso.
# Borra esta nota después de leerla.

SECTIONS = (
    {"key": "cashier", "title": "Caja", "description": "Cobro y entrega de cambio a repartidores.", "url_name": "cashier:cashier_board"},
    {"key": "tables", "title": "Mesas", "description": "Atención y cuentas de mesas.", "url_name": "tables:table_map"},
    {"key": "orders", "title": "Pedidos", "description": "Pedidos internos y externos.", "url_name": "orders:order_list"},
    {"key": "customers", "title": "Clientes", "description": "Agenda de clientes y domicilios.", "url_name": "orders:customer_list"},
    {"key": "deliveries", "title": "Repartos", "description": "Asignación y seguimiento de entregas.", "url_name": "deliveries:delivery_board"},
    {"key": "reports", "title": "Reportes", "description": "Información administrativa.", "url_name": "internal_portal:reports"},
    {"key": "menu", "title": "Menú", "description": "Categorías y productos.", "url_name": "menu:configuration"},
)
