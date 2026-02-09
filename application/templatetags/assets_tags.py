from django import template
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()

# CSP is now fully strict, so no nonce is needed for static assets

