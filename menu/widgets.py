from django.forms.widgets import ClearableFileInput


class ProductImageInput(ClearableFileInput):
    template_name = "menu/widgets/product_image_input.html"
