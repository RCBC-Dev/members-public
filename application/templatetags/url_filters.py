from django import template
from urllib.parse import urlencode

register = template.Library()


@register.simple_tag(takes_context=True)
def build_filter_url(context, **kwargs):
    """
    Build a clean URL with only non-empty parameters.
    
    Usage: {% build_filter_url member=enquiry.member.id %}
    
    This will:
    1. Take all current GET parameters
    2. Remove the parameter being set (e.g., 'member')
    3. Add the new parameter value
    4. Remove any empty parameters from the final URL
    """
    request = context['request']
    
    # Start with current GET parameters
    params = dict(request.GET.items())
    
    # Update with new parameters, removing the key if it's being set
    for key, value in kwargs.items():
        if key in params:
            del params[key]
        if value:  # Only add non-empty values
            params[key] = value
    
    # Remove empty parameters
    clean_params = {k: v for k, v in params.items() if v and str(v).strip()}
    
    # Build the URL
    if clean_params:
        return '?' + urlencode(clean_params)
    else:
        return '?'
