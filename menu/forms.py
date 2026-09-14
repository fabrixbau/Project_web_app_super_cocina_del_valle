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

from .models import (
    Category, DailyMenu, DailyProductStock, MealPackage, Product, ProductOption,
    ProductOptionGroup,
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
            "image_position_y", "image_zoom", "is_available",
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
        fields = ("name", "selection_type", "is_required", "sort_order")
        labels = {
            "name": "Nombre del grupo",
            "selection_type": "Forma de elegir",
            "is_required": "El cliente o mesero debe conservar al menos una opción",
            "sort_order": "Orden visual",
        }
        help_texts = {
            "selection_type": "Usa varias para ingredientes que pueden quitarse; una para elegir entre alternativas.",
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
        if (
            self.instance.pk
            and cleaned_data.get("selection_type") == ProductOptionGroup.SelectionType.SINGLE
            and self.instance.options.filter(is_default=True).count() > 1
        ):
            self.add_error(
                "selection_type",
                "Antes de cambiar a una opción, deja un solo ingrediente marcado como estándar.",
            )
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

    def clean_is_default(self):
        is_default = self.cleaned_data["is_default"]
        group = self.instance.group
        if (
            is_default
            and group.selection_type == ProductOptionGroup.SelectionType.SINGLE
            and group.options.filter(is_default=True).exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError("Un grupo de elección única solo puede tener una opción estándar.")
        return is_default

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


class DailyMenuForm(forms.ModelForm):
    STOCK_FIELDS = (
        "water_product", "chicken_consomme", "variable_first_course",
        "second_course_one", "second_course_two", "chicken_stew", "beef_stew",
        "varied_stew", "beans_order",
    )
    CHANNELS = (DailyProductStock.Channel.TABLE, DailyProductStock.Channel.ORDERS)
    SUPPLIES = (
        (DailyProductStock.ItemKind.TORTILLAS, "Tortillas"),
        (DailyProductStock.ItemKind.BREAD, "Bolillos"),
    )

    class Meta:
        model = DailyMenu
        fields = (
            "date", "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
            "beans_order",
        )
        labels = {
            "date": "Fecha",
            "water_product": "Agua del día",
            "chicken_consomme": "Sopa principal",
            "variable_first_course": "Segunda opción de sopa",
            "second_course_one": "Segundo tiempo · opción 1",
            "second_course_two": "Segundo tiempo · opción 2",
            "chicken_stew": "Guisado de pollo",
            "beef_stew": "Guisado de res",
            "varied_stew": "Guisado variado",
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
            "chicken_stew": Product.ComponentType.CHICKEN_STEW,
            "beef_stew": Product.ComponentType.BEEF_STEW,
            "varied_stew": Product.ComponentType.VARIED_STEW,
            "beans_order": Product.ComponentType.COMPLEMENT,
        }
        for field_name, component_type in field_types.items():
            self.fields[field_name].queryset = Product.objects.filter(
                component_type=component_type,
                is_available=True,
            ).order_by("name")
            self.fields[field_name].empty_label = "Sin seleccionar"
            self.fields[field_name].widget.attrs["data-searchable-select"] = ""
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
        self.fields["chicken_consomme"].widget.attrs["autocomplete"] = "off"
        if not self.is_bound and not self.instance.pk:
            default_soup = self.fields["chicken_consomme"].queryset.filter(
                component_type=Product.ComponentType.CHICKEN_CONSOMME,
            ).first()
            if default_soup:
                self.initial["chicken_consomme"] = default_soup.pk

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
            pieces = DailyProductStock.ChickenPiece.choices if field_name == "chicken_stew" else (("", ""),)
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
        for field_name in self.STOCK_FIELDS:
            if not cleaned_data.get(field_name):
                continue
            pieces = DailyProductStock.ChickenPiece.values if field_name == "chicken_stew" else ("",)
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

    def save_stocks(self):
        """Persist the channel allocation after the DailyMenu instance has been saved."""
        desired = []
        for field_name in self.STOCK_FIELDS:
            product = self.cleaned_data.get(field_name)
            if not product:
                continue
            pieces = DailyProductStock.ChickenPiece.values if field_name == "chicken_stew" else ("",)
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
            if stock and stock.movements.exists() and stock.initial_quantity != quantity:
                raise forms.ValidationError(
                    f"{stock.item_name} ya tiene movimientos. Cambia su existencia mediante un ajuste de inventario."
                )
            if not stock:
                stock = DailyProductStock(**{key: value for key, value in lookup.items() if key != "product__isnull"})
            stock.daily_menu = self.instance
            stock.initial_quantity = quantity
            stock.low_stock_threshold = threshold
            stock.save()
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

    def __init__(self, *args, package, daily_menu, **kwargs):
        super().__init__(*args, **kwargs)
        self.package = package
        self.daily_menu = daily_menu
        self.fields["first_course"].queryset = Product.objects.filter(
            pk__in=[product.pk for product in daily_menu.first_course_options if product], is_available=True
        ).order_by("name")
        self.fields["second_course"].queryset = Product.objects.filter(
            pk__in=[product.pk for product in daily_menu.second_course_options if product], is_available=True
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
        self.fields["main_course"].queryset = Product.objects.filter(
            pk__in=main_ids, is_available=True
        ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        main_course = cleaned_data.get("main_course")
        if main_course and main_course.pk == self.daily_menu.chicken_stew_id:
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
