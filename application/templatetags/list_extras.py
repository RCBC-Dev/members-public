from django import template
from ..utils import calculate_business_days, calculate_calendar_days

register = template.Library()

@register.filter
def list_index(value, arg):
    try:
        return value[int(arg)]
    except (IndexError, ValueError, TypeError):
        return ''

@register.filter
def days_between(start_date, end_date):
    """Calculate calendar days between two dates."""
    return calculate_calendar_days(start_date, end_date)

@register.filter
def business_days_between(start_date, end_date):
    """Calculate business days between two dates (excluding weekends)."""
    return calculate_business_days(start_date, end_date)

@register.filter
def working_days_between(start_date, end_date):
    """
    Calculate working days between two dates (excluding weekends and UK holidays).
    This is a placeholder for future enhancement - currently same as business_days_between.
    """
    # For now, just exclude weekends
    # TODO: Add UK holiday exclusions using python-holidays library
    return calculate_business_days(start_date, end_date)

@register.filter
def resolution_time_color(days):
    """Get CSS color class for resolution time."""
    if days is None:
        return ''
    try:
        days = int(days)
        if days <= 1:
            return 'text-success'
        elif days <= 5:
            return 'text-warning'
        else:
            return 'text-danger'
    except (ValueError, TypeError):
        return ''

@register.filter
def working_days_due_date(created_at, days=5):
    """Calculate due date using working days."""
    from ..utils import calculate_working_days_due_date
    return calculate_working_days_due_date(created_at, days)

@register.inclusion_tag('partials/resolution_time.html')
def resolution_time_display(enquiry, show_tooltip=True):
    """Display resolution time for a closed enquiry with color coding."""
    if enquiry.status != 'closed' or not enquiry.closed_at:
        return {'show_time': False}
    
    business_days = calculate_business_days(enquiry.created_at, enquiry.closed_at)
    calendar_days = calculate_calendar_days(enquiry.created_at, enquiry.closed_at)
    
    if business_days is None:
        return {'show_time': False}
    
    return {
        'show_time': True,
        'business_days': business_days,
        'calendar_days': calendar_days,
        'color_class': resolution_time_color(business_days),
        'show_tooltip': show_tooltip
    }
