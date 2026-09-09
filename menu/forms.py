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
    Category, DailyMenu, MealPackage, Product, ProductOption, ProductOptionGroup,
)


MAX_IMAGE_SIZE = 4 * 1024 * 1024


def validate_image_size(image):
    if image and image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError("La imagen no puede superar 4 MB.")
    return image


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = (
            "name", "image", "show_on_public_breakfast", "show_on_public_lunch",
            "show_on_table_breakfast", "show_on_table_lunch", "show_table_packages",
        )
        labels = {
            "name": "Nombre", "image": "Imagen",
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

    def clean_image(self):
        return validate_image_size(self.cleaned_data.get("image"))


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "category", "name", "price", "description", "image", "is_available",
            "component_type", "service_periods", "is_sold_individually",
            "eligible_for_executive_meal", "packaging_kind", "sort_order",
        )
        labels = {
            "category": "Categoría", "name": "Nombre", "price": "Precio",
            "description": "Descripción", "image": "Imagen",
            "is_available": "Disponible", "component_type": "Función del producto",
            "service_periods": "Periodos en que se vende",
            "is_sold_individually": "Se puede vender por orden",
            "eligible_for_executive_meal": "Elegible para comida ejecutiva",
            "packaging_kind": "Uso como envase",
            "sort_order": "Orden visual",
        }
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "service_periods": forms.CheckboxSelectMultiple(),
        }
        help_texts = {
            "category": "Determina en qué pestaña se encontrará el producto.",
            "component_type": "Indica si participa en el menú diario, en un paquete o como producto general.",
            "service_periods": "Sin selección no se limita por periodo. Mesas ignora el horario, pero el menú público sí lo aplica.",
            "is_available": "Apágalo para retirar temporalmente el producto de la venta.",
            "is_sold_individually": "Actívalo para que aparezca como producto suelto dentro de su categoría.",
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


class DailyMenuForm(forms.ModelForm):
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
            "chicken_consomme": "Consomé de pollo",
            "variable_first_course": "Primera opción variable",
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
        field_types = {
            "water_product": Product.ComponentType.BEVERAGE,
            "chicken_consomme": Product.ComponentType.CHICKEN_CONSOMME,
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

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("second_course_one") == cleaned_data.get("second_course_two") and cleaned_data.get("second_course_one"):
            self.add_error("second_course_two", "Selecciona una opción diferente.")
        return cleaned_data


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
