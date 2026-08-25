from django import forms

from .models import Category, DailyMenu, Product


MAX_IMAGE_SIZE = 4 * 1024 * 1024


def validate_image_size(image):
    if image and image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError("La imagen no puede superar 4 MB.")
    return image


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "image", "sort_order")
        labels = {"name": "Nombre", "image": "Imagen", "sort_order": "Orden visual"}

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
            "eligible_for_executive_meal", "sort_order",
        )
        labels = {
            "category": "Categoría", "name": "Nombre", "price": "Precio",
            "description": "Descripción", "image": "Imagen",
            "is_available": "Disponible", "component_type": "Función del producto",
            "service_periods": "Periodos en que se vende",
            "is_sold_individually": "Se puede vender por orden",
            "eligible_for_executive_meal": "Elegible para comida ejecutiva",
            "sort_order": "Orden visual",
        }
        widgets = {
            "price": forms.NumberInput(attrs={"min": "0", "step": "0.50"}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "service_periods": forms.CheckboxSelectMultiple(),
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


class DailyMenuForm(forms.ModelForm):
    class Meta:
        model = DailyMenu
        fields = (
            "date", "water_product", "chicken_consomme", "variable_first_course",
            "second_course_one", "second_course_two", "chicken_stew", "beef_stew", "varied_stew",
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
