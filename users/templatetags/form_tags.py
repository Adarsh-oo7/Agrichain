# Place this in yourapp/templatetags/form_tags.py
from django import template
register = template.Library()

@register.filter(name='add_attr')
def add_attr(field, attr_val):
    """
    Add an attribute to a form field
    Usage: {{ field|add_attr:"attribute:value" }}
    """
    attr, val = attr_val.split(':')
    attrs = field.field.widget.attrs
    attrs[attr] = val
    return field

@register.filter(name='add_class')
def add_class(field, class_name):
    """
    Add a CSS class to a form field
    Usage: {{ field|add_class:"class-name" }}
    """
    return add_attr(field, f"class:{class_name}")

@register.filter(name='add_id_prefix')
def add_id_prefix(field, prefix):
    """
    Add a prefix to the field ID to ensure uniqueness
    Usage: {{ field|add_id_prefix:"gov_" }}
    """
    widget = field.field.widget
    
    # Get the current ID attributes
    attrs = widget.attrs
    
    # If the field has an ID, add prefix
    if 'id' in attrs:
        attrs['id'] = f"{prefix}{attrs['id']}"
    else:
        # If no ID yet, create one based on the field name
        field_id = field.auto_id
        if field_id:
            # Strip the 'id_' prefix Django automatically adds
            field_id = field_id.replace('id_', '')
            attrs['id'] = f"{prefix}id_{field_id}"
    
    return field