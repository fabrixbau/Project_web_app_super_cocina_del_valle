# NOTA TEMPORAL PARA APRENDIZAJE:
# El formulario de categoría expone el orden y visibilidad de ambos modos de mesas.
# Así Administración controla la interfaz sin modificar código. Borra esta nota al leerla.
# Orden de frijoles es un complemento opcional y no uno de los tres tiempos del paquete.
# Los órdenes ya no se capturan como números aquí: se administran arrastrando todas las categorías.
# ProductForm agrega ayudas cortas para explicar qué controla cada regla sin exigir que
# quien administra el menú conozca los nombres internos del sistema. Borra esta nota.
# Los nuevos formularios separan grupo e ingrediente: el grupo define cuántas opciones se
# eligen y cada opción define si es estándar, disponible y si cobra extra. Borra esta nota.

from django import forms
from django.db.models import Case, IntegerField, Sum, Value, When

from .models import (
    Category, DailyMenu, DailyProductStock, MealPackage, Product, ProductOption,
    ProductOptionGroup, StockMovement,
)
from .widgets import ProductImageInput


MAX_IMAGE_SIZE = 4 * 1024 * 1024


def validate_image_size(image):
    if image and image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError("La imagen no puede superar 4 MB.")
    return image


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = (
            "name", "show_on_public_breakfast", "show_on_public_lunch",
            "show_on_table_breakfast", "show_on_table_lunch", "show_table_packages",
        )
        labels = {
            "name": "Nombre",
            "show_on_public_breakfast": "Mostrar a clientes · desayunos",
            "show_on_public_lunch": "Mostrar a clientes · comida",
            "show_on_table_breakfast": "Mostrar en mesas · desayunos",
            "show_on_table_lunch": "Mostrar en mesas · comida",
            "show_table_packages": "Mostrar paquetes al elegir esta categoría",
        }

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        duplicate = Category.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Ya existe una categoría con este nombre.")
        return name

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "category", "name", "price", "description", "image", "image_position_x",
            "image_position_y", "image_zoom", "is_available", "show_to_customers", "show_in_qr_menu",
            "component_type", "service_periods", "is_sold_individually", "uses_bread_stock",
            "eligible_for_executive_meal", "packaging_kind", "sort_order",
        )
        labels = {
            "category": "Categoría", "name": "Nombre", "price": "Precio",
            "description": "Descripción", "image": "Imagen",
            "is_available": "Disponible", "component_type": "Función del producto",
            "service_periods": "Periodos en que se vende",
            "is_sold_individually": "Se puede vender por orden",
            "uses_bread_stock": "Descontar del conteo de bolillos",
            "eligible_for_executive_meal": "Elegible para comida ejecutiva",
            "packaging_kind": "Uso como envase",
            "sort_order": "Orden visual",
        }
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "image": ProductImageInput(attrs={"accept": "image/*"}),
            "image_position_x": forms.HiddenInput(),
            "image_position_y": forms.HiddenInput(),
            "image_zoom": forms.HiddenInput(),
            "service_periods": forms.CheckboxSelectMultiple(),
        }
        help_texts = {
            "category": "Determina en qué pestaña se encontrará el producto.",
            "component_type": "Usa Agua del menú diario para las aguas rotativas. Jugos y bebidas fijas deben conservar Bebida.",
            "service_periods": "Sin selección no se limita por periodo. Mesas ignora el horario, pero el menú público sí lo aplica.",
            "is_available": "Apágalo para retirar temporalmente el producto de la venta.",
            "is_sold_individually": "Actívalo para que aparezca como producto suelto dentro de su categoría.",
            "uses_bread_stock": "Actívalo únicamente en el producto Bolillo; cada unidad vendida descuenta un bolillo del inventario de su canal.",
            "eligible_for_executive_meal": "Solo aplica a productos cuya función sea Producto de plancha.",
            "packaging_kind": "Clasifícalo para mostrarlo en Envases; estas opciones nunca aparecen en el menú público.",
            "sort_order": "Los números menores aparecen primero dentro de la categoría.",
        }

    CUSTOMER_VISIBILITY_CHOICES = (
        ("yes", "Sí, mostrarlo en el menú para clientes"),
        ("no", "No, sólo para uso interno"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Al crear un producto la pregunta no trae respuesta marcada: hay que decidir
        # explícitamente si el cliente lo verá en /pedir/.
        is_new = not self.instance.pk
        self.fields["show_to_customers"] = forms.TypedChoiceField(
            label="¿Mostrar en el menú para clientes?",
            choices=self.CUSTOMER_VISIBILITY_CHOICES,
            coerce=lambda value: value == "yes",
            widget=forms.RadioSelect,
            help_text="Ocultarlo lo retira de /pedir/ (también como opción de paquetes); Mesas y Pedidos internos no cambian.",
            error_messages={"required": "Indica si el cliente podrá ver este producto."},
        )
        # ModelForm toma el booleano del producto como valor inicial; el radio usa "yes"/"no".
        if is_new and not self.is_bound:
            self.initial.pop("show_to_customers", None)
        elif not is_new:
            self.initial["show_to_customers"] = "yes" if self.instance.show_to_customers else "no"

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        category = self.cleaned_data.get("category")
        duplicate = Product.objects.filter(category=category, name__iexact=name).exclude(pk=self.instance.pk)
        if category and duplicate.exists():
            raise forms.ValidationError("Ya existe un producto con este nombre en la categoría.")
        return name

    def clean_image(self):
        return validate_image_size(self.cleaned_data.get("image"))

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("eligible_for_executive_meal") and cleaned_data.get("component_type") != Product.ComponentType.GRILL:
            self.add_error("eligible_for_executive_meal", "Solo los productos de plancha pueden marcarse para comida ejecutiva.")
        return cleaned_data


class ProductOptionGroupForm(forms.ModelForm):
    class Meta:
        model = ProductOptionGroup
        # Ya no se elige la forma: todos los grupos permiten elegir varias opciones.
        fields = ("name", "is_required", "sort_order")
        labels = {
            "name": "Nombre del grupo",
            "is_required": "El cliente o mesero debe conservar al menos una opción",
            "sort_order": "Orden visual",
        }
        help_texts = {
            "is_required": "Por ejemplo, una proteína obligatoria. Déjalo apagado si puede pedirse sin esos ingredientes.",
            "sort_order": "Los grupos con números menores aparecen primero.",
        }

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        duplicate = ProductOptionGroup.objects.filter(
            product=self.instance.product, name__iexact=name,
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Este producto ya tiene un grupo con ese nombre.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        self.instance.selection_type = ProductOptionGroup.SelectionType.MULTIPLE
        return cleaned_data


class ProductOptionForm(forms.ModelForm):
    class Meta:
        model = ProductOption
        fields = ("name", "price_adjustment", "replacement_pair", "is_default", "is_available", "sort_order")
        labels = {
            "name": "Ingrediente u opción",
            "price_adjustment": "Cargo adicional",
            "replacement_pair": "Par de sustitución",
            "is_default": "Incluido en la preparación estándar",
            "is_available": "Disponible para seleccionar",
            "sort_order": "Orden visual",
        }
        widgets = {
            "price_adjustment": forms.NumberInput(attrs={"step": "0.50"}),
        }
        help_texts = {
            "price_adjustment": "Usa 0 cuando está incluido. Puede ser positivo para cobrar un extra.",
            "replacement_pair": "Usa la misma clave en alternativas equivalentes, por ejemplo Aderezo para crema y mayonesa.",
            "is_default": "Si se desmarca al ordenar, el ticket identificará el producto como Modificado.",
            "sort_order": "Los números menores aparecen primero dentro del grupo.",
        }

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        duplicate = ProductOption.objects.filter(
            group=self.instance.group, name__iexact=name,
        ).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError("Este grupo ya contiene una opción con ese nombre.")
        return name


    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_default") and not cleaned_data.get("is_available"):
            self.add_error(
                "is_available", "Una opción incluida en la preparación estándar debe estar disponible.",
            )
        return cleaned_data


class ProductOptionGroupCopyForm(forms.Form):
    source_group = forms.ModelChoiceField(
        label="Grupo que deseas pegar",
        queryset=ProductOptionGroup.objects.none(),
        empty_label="Selecciona un grupo existente",
        help_text="Se copiarán ingredientes, cargos y preparación estándar. La copia podrá editarse sin cambiar el producto original.",
    )

    def __init__(self, *args, target_product, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_group"].queryset = ProductOptionGroup.objects.exclude(
            product=target_product,
        ).select_related("product").prefetch_related("options").order_by(
            "product__name", "sort_order", "name",
        )


class StockAdjustmentForm(forms.Form):
    stock = forms.ModelChoiceField(label="Existencia", queryset=DailyProductStock.objects.none())
    quantity = forms.IntegerField(
        label="Cambio de cantidad",
        help_text="Usa un número positivo para agregar o negativo para descontar.",
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "step": "1"}),
    )
    note = forms.CharField(label="Motivo", max_length=250)

    def __init__(self, *args, stock_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stock"].queryset = stock_queryset if stock_queryset is not None else DailyProductStock.objects.none()
        self.fields["stock"].widget.attrs["data-searchable-select"] = ""

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity == 0:
            raise forms.ValidationError("El ajuste no puede ser cero.")
        return quantity


class StockTransferForm(forms.Form):
    source = forms.ModelChoiceField(label="Desde", queryset=DailyProductStock.objects.none())
    target = forms.ModelChoiceField(label="Hacia", queryset=DailyProductStock.objects.none())
    quantity = forms.IntegerField(
        label="Cantidad", min_value=1,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "1", "step": "1"}),
    )
    note = forms.CharField(label="Motivo", max_length=250)

    def __init__(self, *args, stock_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = stock_queryset if stock_queryset is not None else DailyProductStock.objects.none()
        self.fields["source"].queryset = queryset
        self.fields["target"].queryset = queryset
        self.fields["source"].widget.attrs["data-searchable-select"] = ""
        self.fields["target"].widget.attrs["data-searchable-select"] = ""

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source")
        target = cleaned.get("target")
        if source and target and source.pk == target.pk:
            self.add_error("target", "Selecciona otro canal.")
        return cleaned


class FixedStockForm(forms.Form):
    product = forms.ModelChoiceField(
        label="Producto del menú fijo",
        queryset=Product.objects.filter(is_available=True).order_by("category__name", "name"),
    )
    quantity = forms.IntegerField(
        label="Cantidad disponible", min_value=0,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
    )
    low_stock_threshold = forms.IntegerField(
        label="Avisar cuando queden", min_value=0, initial=10,
        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].widget.attrs["data-searchable-select"] = ""


MENU_ADJUSTMENT_NOTE = "Ajuste desde el menú diario"


class DailyMenuForm(forms.ModelForm):
    STOCK_FIELDS = (
        "water_product", "chicken_consomme", "variable_first_course",
        "second_course_one", "second_course_two", "beans_order",
    )
    # Tercer tiempo: hasta 12 guisados (stew_1 … stew_12), cada uno de cualquier tipo.
    STEW_SLOTS = tuple(range(1, DailyMenu.MAX_STEWS + 1))
    DEFAULT_STEW_ROWS = 3
    CHANNELS = (DailyProductStock.Channel.TABLE, DailyProductStock.Channel.ORDERS)
    SUPPLIES = (
        (DailyProductStock.ItemKind.TORTILLAS, "Tortillas"),
        (DailyProductStock.ItemKind.BREAD, "Bolillos"),
    )

    class Meta:
        model = DailyMenu
        fields = (
            "date", "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "beans_order",
        )
        labels = {
            "date": "Fecha",
            "water_product": "Agua del día",
            "chicken_consomme": "Sopa principal",
            "variable_first_course": "Segunda opción de sopa",
            "second_course_one": "Segundo tiempo · opción 1",
            "second_course_two": "Segundo tiempo · opción 2",
            "beans_order": "Orden de frijoles",
        }
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stock_rows = []
        field_types = {
            "water_product": Product.ComponentType.DAILY_WATER,
            "variable_first_course": Product.ComponentType.VARIABLE_FIRST_COURSE,
            "second_course_one": Product.ComponentType.SECOND_COURSE,
            "second_course_two": Product.ComponentType.SECOND_COURSE,
            "beans_order": Product.ComponentType.COMPLEMENT,
        }
        for field_name, component_type in field_types.items():
            self.fields[field_name].queryset = Product.objects.filter(
                component_type=component_type,
                is_available=True,
            ).order_by("name")
            self.fields[field_name].empty_label = "Sin seleccionar"
            self.fields[field_name].widget.attrs["data-searchable-select"] = ""
            self.fields[field_name].widget.attrs["data-click-toggle-select"] = ""
            self.fields[field_name].widget.attrs["autocomplete"] = "off"
        self.fields["water_product"].queryset = Product.objects.filter(
            component_type=Product.ComponentType.DAILY_WATER,
            category__name__iexact="Bebidas frías",
            is_available=True,
        ).order_by("name")
        soup_types = (
            Product.ComponentType.CHICKEN_CONSOMME,
            Product.ComponentType.VARIABLE_FIRST_COURSE,
        )
        self.fields["chicken_consomme"].queryset = Product.objects.filter(
            component_type__in=soup_types, is_available=True,
        ).order_by("component_type", "name")
        self.fields["chicken_consomme"].empty_label = "Sin seleccionar"
        self.fields["chicken_consomme"].widget.attrs["data-searchable-select"] = ""
        self.fields["chicken_consomme"].widget.attrs["data-click-toggle-select"] = ""
        self.fields["chicken_consomme"].widget.attrs["autocomplete"] = "off"
        if not self.is_bound and not self.instance.pk:
            default_soup = self.fields["chicken_consomme"].queryset.filter(
                component_type=Product.ComponentType.CHICKEN_CONSOMME,
            ).first()
            if default_soup:
                self.initial["chicken_consomme"] = default_soup.pk

        stew_queryset = Product.objects.filter(
            component_type__in=DailyMenu.STEW_TYPES, is_available=True,
        ).order_by("name")
        current_stews = self.instance.stew_products if self.instance.pk else []
        self.chicken_stew_product_ids = list(stew_queryset.filter(
            component_type=Product.ComponentType.CHICKEN_STEW,
        ).values_list("pk", flat=True))
        for slot in self.STEW_SLOTS:
            name = f"stew_{slot}"
            self.fields[name] = forms.ModelChoiceField(
                label=f"Guisado {slot}", queryset=stew_queryset, required=False, empty_label="Sin seleccionar",
            )
            # Sólo el nombre del platillo (sin "Comida corrida · …") para que quepa en la lista.
            self.fields[name].label_from_instance = lambda product: product.name
            for attr in ("data-searchable-select", "data-click-toggle-select"):
                self.fields[name].widget.attrs[attr] = ""
            self.fields[name].widget.attrs["autocomplete"] = "off"
            self.fields[name].widget.attrs["data-stew-select"] = str(slot)
            if not self.is_bound and slot <= len(current_stews):
                self.initial[name] = current_stews[slot - 1].pk
        if self.is_bound:
            filled = [slot for slot in self.STEW_SLOTS if self.data.get(f"stew_{slot}")]
        else:
            filled = list(range(1, len(current_stews) + 1))
        self.visible_stew_rows = max([self.DEFAULT_STEW_ROWS, *filled])
        self.stew_rows = [
            {"slot": slot, "field": self[f"stew_{slot}"], "hidden": slot > self.visible_stew_rows}
            for slot in self.STEW_SLOTS
        ]

        channel_labels = dict(DailyProductStock.Channel.choices)
        existing = {}
        if self.instance.pk:
            existing = {
                (stock.product_id, stock.item_kind, stock.channel, stock.chicken_piece): (
                    stock.initial_quantity, stock.low_stock_threshold,
                ) for stock in self.instance.product_stocks.all()
            }
        for field_name in self.STOCK_FIELDS:
            selected_id = self.data.get(field_name) if self.is_bound else getattr(self.instance, f"{field_name}_id", None)
            pieces = (("", ""),)
            for piece, piece_label in pieces:
                label = self.fields[field_name].label
                if piece_label:
                    label = f"{label} · {piece_label}"
                row = {"label": label, "selector": self[field_name], "channels": []}
                for channel in self.CHANNELS:
                    suffix = f"_{piece}" if piece else ""
                    name = f"stock_{field_name}{suffix}_{channel}"
                    threshold_name = f"threshold_{field_name}{suffix}_{channel}"
                    self.fields[name] = forms.IntegerField(
                        label=channel_labels[channel], min_value=0, required=False,
                        initial=0,
                        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                    )
                    self.fields[threshold_name] = forms.IntegerField(
                        label="Avisar cuando queden", min_value=0, required=False, initial=15,
                        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                    )
                    if not self.is_bound and selected_id:
                        values = existing.get(
                            (int(selected_id), DailyProductStock.ItemKind.PRODUCT, channel, piece), (0, 15),
                        )
                        self.initial[name], self.initial[threshold_name] = values
                    row["channels"].append({
                        "label": channel_labels[channel], "quantity": self[name],
                        "threshold": self[threshold_name],
                    })
                self.stock_rows.append(row)
        # Raciones de cada guisado: fila general y, para guisados de pollo, pierna y muslo.
        # Se dibujan las de los 12 renglones; daily-menu-stews.js muestra las que aplican.
        piece_labels = dict(DailyProductStock.ChickenPiece.choices)
        for slot in self.STEW_SLOTS:
            if self.is_bound:
                selected_id = self.data.get(f"stew_{slot}") or None
            else:
                selected_id = current_stews[slot - 1].pk if slot <= len(current_stews) else None
            for piece in ("", *DailyProductStock.ChickenPiece.values):
                row = {
                    "label": f"Guisado {slot}" + (f" · {piece_labels[piece]}" if piece else ""),
                    "selector": None, "channels": [], "stew_slot": slot, "stew_piece": piece,
                }
                for channel in self.CHANNELS:
                    suffix = f"_{piece}" if piece else ""
                    name = f"stock_stew_{slot}{suffix}_{channel}"
                    threshold_name = f"threshold_stew_{slot}{suffix}_{channel}"
                    self.fields[name] = forms.IntegerField(
                        label=channel_labels[channel], min_value=0, required=False, initial=0,
                        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                    )
                    self.fields[threshold_name] = forms.IntegerField(
                        label="Avisar cuando queden", min_value=0, required=False, initial=15,
                        widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                    )
                    if not self.is_bound and selected_id:
                        self.initial[name], self.initial[threshold_name] = existing.get(
                            (int(selected_id), DailyProductStock.ItemKind.PRODUCT, channel, piece), (0, 15),
                        )
                    row["channels"].append({
                        "label": channel_labels[channel], "quantity": self[name], "threshold": self[threshold_name],
                    })
                self.stock_rows.append(row)
        for item_kind, label in self.SUPPLIES:
            row = {"label": label, "selector": None, "channels": []}
            for channel in self.CHANNELS:
                name = f"stock_{item_kind}_{channel}"
                threshold_name = f"threshold_{item_kind}_{channel}"
                values = existing.get((None, item_kind, channel, ""), (0, 15))
                self.fields[name] = forms.IntegerField(
                    label=channel_labels[channel], min_value=0, required=True,
                    widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                    initial=values[0],
                )
                self.fields[threshold_name] = forms.IntegerField(
                    label="Avisar cuando queden", min_value=0, required=False, initial=values[1],
                    widget=forms.NumberInput(attrs={"inputmode": "numeric", "min": "0", "step": "1"}),
                )
                row["channels"].append({
                    "label": channel_labels[channel], "quantity": self[name],
                    "threshold": self[threshold_name],
                })
            self.stock_rows.append(row)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("second_course_one") == cleaned_data.get("second_course_two") and cleaned_data.get("second_course_one"):
            self.add_error("second_course_two", "Selecciona una opción diferente.")
        if cleaned_data.get("chicken_consomme") == cleaned_data.get("variable_first_course") and cleaned_data.get("chicken_consomme"):
            self.add_error("variable_first_course", "Selecciona una sopa diferente.")
        stews, seen = [], {}
        for slot in self.STEW_SLOTS:
            product = cleaned_data.get(f"stew_{slot}")
            if not product:
                continue
            if product.pk in seen:
                self.add_error(f"stew_{slot}", f"Este guisado ya está en el renglón {seen[product.pk]}.")
                continue
            seen[product.pk] = slot
            stews.append((slot, product))
            pieces = DailyProductStock.ChickenPiece.values if product.component_type == Product.ComponentType.CHICKEN_STEW else ("",)
            for piece in pieces:
                suffix = f"_{piece}" if piece else ""
                values = []
                for channel in self.CHANNELS:
                    quantity_name = f"stock_stew_{slot}{suffix}_{channel}"
                    quantity = cleaned_data.get(quantity_name)
                    if quantity is None:
                        self.add_error(quantity_name, "Indica una cantidad, aunque sea cero.")
                    else:
                        values.append(quantity)
                if values and not any(values):
                    item_label = dict(DailyProductStock.ChickenPiece.choices).get(piece, "producto").lower()
                    self.add_error(
                        f"stock_stew_{slot}{suffix}_{self.CHANNELS[0]}",
                        f"Distribuye al menos una ración de {item_label}.",
                    )
        cleaned_data["stews"] = stews
        for field_name in self.STOCK_FIELDS:
            if not cleaned_data.get(field_name):
                continue
            pieces = ("",)
            for piece in pieces:
                suffix = f"_{piece}" if piece else ""
                values = []
                for channel in self.CHANNELS:
                    quantity_name = f"stock_{field_name}{suffix}_{channel}"
                    quantity = cleaned_data.get(quantity_name)
                    if quantity is None:
                        self.add_error(quantity_name, "Indica una cantidad, aunque sea cero.")
                    else:
                        values.append(quantity)
                if values and not any(values):
                    item_label = dict(DailyProductStock.ChickenPiece.choices).get(piece, "producto").lower()
                    self.add_error(
                        f"stock_{field_name}{suffix}_{self.CHANNELS[0]}",
                        f"Distribuye al menos una ración de {item_label}.",
                    )
        for item_kind, label in self.SUPPLIES:
            values = [cleaned_data.get(f"stock_{item_kind}_{channel}") for channel in self.CHANNELS]
            if all(value is not None for value in values) and not any(values):
                self.add_error(f"stock_{item_kind}_{self.CHANNELS[0]}", f"Distribuye al menos una ración de {label.lower()}.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            instance.set_stews([product for _slot, product in self.cleaned_data.get("stews", [])])
        return instance

    def save_stocks(self, actor=None):
        """Persist the channel allocation after the DailyMenu instance has been saved.

        Si la existencia de ese día ya tiene movimientos (ventas registradas), no se bloquea:
        se conserva su cantidad inicial y se registra un ajuste de inventario por la
        diferencia, así el historial queda intacto y el disponible queda como se capturó.
        """
        from .inventory import adjust_stock
        desired = []
        for slot, product in self.cleaned_data.get("stews", []):
            pieces = DailyProductStock.ChickenPiece.values if product.component_type == Product.ComponentType.CHICKEN_STEW else ("",)
            for piece in pieces:
                suffix = f"_{piece}" if piece else ""
                for channel in self.CHANNELS:
                    desired.append((
                        DailyProductStock.ItemKind.PRODUCT, product, channel, piece,
                        self.cleaned_data[f"stock_stew_{slot}{suffix}_{channel}"],
                        self.cleaned_data.get(f"threshold_stew_{slot}{suffix}_{channel}") or 0,
                    ))
        for field_name in self.STOCK_FIELDS:
            product = self.cleaned_data.get(field_name)
            if not product:
                continue
            pieces = ("",)
            for piece in pieces:
                suffix = f"_{piece}" if piece else ""
                for channel in self.CHANNELS:
                    desired.append((
                        DailyProductStock.ItemKind.PRODUCT, product, channel, piece,
                        self.cleaned_data[f"stock_{field_name}{suffix}_{channel}"],
                        self.cleaned_data.get(f"threshold_{field_name}{suffix}_{channel}") or 0,
                    ))
        for item_kind, _label in self.SUPPLIES:
            for channel in self.CHANNELS:
                desired.append((
                    item_kind, None, channel, "", self.cleaned_data[f"stock_{item_kind}_{channel}"],
                    self.cleaned_data.get(f"threshold_{item_kind}_{channel}") or 0,
                ))

        keep_ids = []
        for item_kind, product, channel, chicken_piece, quantity, threshold in desired:
            lookup = {
                "date": self.instance.date, "item_kind": item_kind,
                "channel": channel, "chicken_piece": chicken_piece,
            }
            if product:
                lookup["product"] = product
            else:
                lookup["product__isnull"] = True
            stock = DailyProductStock.objects.filter(**lookup).first()
            adjustment = 0
            if stock and stock.movements.exists():
                # Las raciones "efectivas" de esa existencia = inicial + ajustes que ya hizo el
                # menú. Sólo se ajusta la diferencia contra eso (antes se volvía a sumar en
                # cada guardado y las raciones crecían de más).
                menu_adjustments = stock.movements.filter(
                    reason=StockMovement.Reason.ADJUSTMENT, note__startswith=MENU_ADJUSTMENT_NOTE,
                ).aggregate(total=Sum("quantity"))["total"] or 0
                adjustment = quantity - (stock.initial_quantity + menu_adjustments)
                quantity = stock.initial_quantity
            if not stock:
                stock = DailyProductStock(**{key: value for key, value in lookup.items() if key != "product__isnull"})
            stock.daily_menu = self.instance
            stock.initial_quantity = quantity
            stock.low_stock_threshold = threshold
            stock.save()
            if adjustment:
                adjust_stock(
                    stock=stock, quantity=adjustment, actor=actor,
                    note=f"{MENU_ADJUSTMENT_NOTE} ({'+' if adjustment > 0 else ''}{adjustment})",
                )
            from notifications.services import sync_stock_alert
            sync_stock_alert(stock)
            keep_ids.append(stock.pk)
        self.instance.product_stocks.filter(movements__isnull=True).exclude(pk__in=keep_ids).delete()


class MealPackageForm(forms.ModelForm):
    class Meta:
        model = MealPackage
        fields = (
            "name", "description", "price_without_water", "price_with_water",
            "table_refill_price", "is_active",
        )
        labels = {
            "name": "Nombre visible",
            "description": "Descripción breve",
            "price_without_water": "Precio sin agua",
            "price_with_water": "Precio con agua",
            "table_refill_price": "Cargo por refill extra en mesa",
            "is_active": "Paquete disponible",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "price_without_water": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
            "price_with_water": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
            "table_refill_price": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
        }


class PackageSelectionForm(forms.Form):
    class OrderType:
        PICKUP = "pickup"
        DELIVERY = "delivery"

    ORDER_TYPE_CHOICES = (
        ("pickup", "Recoger en la fonda"),
        ("delivery", "Entrega a domicilio"),
    )
    YES_NO_CHOICES = (("yes", "Sí"), ("no", "No"))

    order_type = forms.ChoiceField(label="Tipo de pedido", choices=ORDER_TYPE_CHOICES)
    first_course = forms.ModelChoiceField(label="Primer tiempo", queryset=Product.objects.none())
    second_course = forms.ModelChoiceField(label="Segundo tiempo", queryset=Product.objects.none())
    main_course = forms.ModelChoiceField(label="Tercer tiempo", queryset=Product.objects.none())
    chicken_piece = forms.ChoiceField(
        label="Pieza de pollo (si elegiste guisado de pollo)",
        choices=(("", "No aplica"), ("leg", "Pierna"), ("thigh", "Muslo")),
        required=False,
    )
    with_water = forms.BooleanField(label="Con agua del día", required=False)
    tortillas = forms.ChoiceField(label="¿Lleva tortillas?", choices=YES_NO_CHOICES)
    beans = forms.ChoiceField(label="¿Lleva frijoles?", choices=YES_NO_CHOICES)

    def __init__(self, *args, package, daily_menu, customers_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.package = package
        self.daily_menu = daily_menu
        self.customers_only = customers_only
        # En /pedir/ sólo se ofrecen componentes visibles para clientes; Mesas y Pedidos
        # internos (customers_only=False) conservan todas las opciones.
        visible = {"show_to_customers": True} if customers_only else {}
        self.fields["first_course"].queryset = Product.objects.filter(
            pk__in=[product.pk for product in daily_menu.first_course_options if product], is_available=True, **visible
        ).order_by("name")
        self.fields["second_course"].queryset = Product.objects.filter(
            pk__in=[product.pk for product in daily_menu.second_course_options if product], is_available=True, **visible
        ).order_by("name")

        if package.package_type == MealPackage.PackageType.RUNNING:
            main_products = daily_menu.stew_options
            self.fields["main_course"].label = "Tercer tiempo · guisado"
        else:
            main_products = Product.objects.filter(
                component_type=Product.ComponentType.GRILL,
                eligible_for_executive_meal=True,
                is_available=True,
            )
            self.fields["main_course"].label = "Tercer tiempo · plancha"
        main_ids = [product.pk for product in main_products if product]
        main_queryset = Product.objects.filter(pk__in=main_ids, is_available=True, **visible)
        if package.package_type == MealPackage.PackageType.RUNNING:
            # Guisados en el orden en que se capturaron en el menú del día.
            main_queryset = main_queryset.order_by(Case(
                *(When(pk=product_id, then=Value(position)) for position, product_id in enumerate(main_ids)),
                output_field=IntegerField(),
            ))
        else:
            main_queryset = main_queryset.order_by("name")
        self.fields["main_course"].queryset = main_queryset

    def clean(self):
        cleaned_data = super().clean()
        main_course = cleaned_data.get("main_course")
        if main_course and self.daily_menu.is_chicken_stew(main_course):
            if not cleaned_data.get("chicken_piece"):
                self.add_error("chicken_piece", "Elige pierna o muslo para el guisado de pollo.")
        elif cleaned_data.get("chicken_piece"):
            self.add_error("chicken_piece", "La pieza solo aplica cuando eliges el guisado de pollo.")
        return cleaned_data

    def calculated_total(self):
        total = (
            self.package.price_with_water
            if self.cleaned_data["with_water"]
            else self.package.price_without_water
        )
        return total
