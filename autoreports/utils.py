from django.contrib.sites.models import Site
from django.db.models import fields as django_fields
from django.db.models.fields.related import RelatedField
from django.db.models.related import RelatedObject
from django.utils.translation import ugettext
from django.utils.translation import ugettext_lazy as _

from autoreports import csv_to_excel

EXPORT_FORMATS = {
    'csv': {
        'file_extension': 'csv',
        'label': _('Report to CSV'),
    },
    'excel': {
        'file_extension': 'xls',
        'label': _('Report to Excel'),
    },
}


CHOICES_ALL = (('icontains', ugettext('Contains')),
               ('lt', ugettext('less than')),
               ('lte', ugettext('less equal than')),
               ('gt', ugettext('great than')),
               ('gte', ugettext('great equal than')),
               ('iexact', ugettext('exact')), )


CHOICES_STR = (('icontains', ugettext('Contains')),
               ('iexact', ugettext('exact')), )


CHOICES_RELATED = (('', ugettext('Contains')), )


CHOICES_INTEGER = (('lt', ugettext('less than')),
                   ('lte', ugettext('less equal than')),
                   ('gt', ugettext('great than')),
                   ('gte', ugettext('great equal than')),
                   ('iexact', ugettext('exact')), )


CHOICES_DATE = CHOICES_INTEGER


CHOICES_BOOLEAN = (('', ugettext('Select')), )


def add_domain(value):
    site = Site.objects.get_current()
    value = 'http://%s%s' %(site.domain, value)
    return value


def get_available_formats():
    formats = {}
    for format, format_data in EXPORT_FORMATS.items():
        if format == 'excel' and not csv_to_excel.HAS_PYEXCELERATOR:
            continue
        formats[format] = format_data
    return formats


def get_fields_from_model(model, prefix=None):
    model_fields = []
    objs_related = []
    fields_related = []
    funcs = []
    prefix = prefix or ''
    for field_name in model._meta.get_all_field_names():
        field = model._meta.get_field_by_name(field_name)[0]
        field_type = 'normal'
        field_name_prefix = field_name
        if prefix:
            field_name_prefix = '%s__%s' % (prefix, field_name)
        if isinstance(field, RelatedObject):
            field_type = prefix and '%s__objs_related' % prefix or 'objs_related'
            objs_related.append({'field': field,
                                 'name': field_name_prefix,
                                 'choices': CHOICES_ALL,
                                 'type': field_type,
                                 'verbose_name': field_name,
                                 'app_label': field.model._meta.app_label,
                                 'module_name': field.model._meta.module_name,
                                 'help_text': ''})
        elif isinstance(field, RelatedField):
            field_type = prefix and '%s__fields_related' % prefix or 'fields_related'
            fields_related.append({'field': field,
                                  'name': field_name_prefix,
                                  'choices': CHOICES_RELATED,
                                  'type': field_type,
                                  'verbose_name': field.verbose_name,
                                  'app_label': field.rel.to._meta.app_label,
                                  'module_name': field.rel.to._meta.module_name,
                                  'help_text': field.help_text})
        else:
            field_type = prefix and '%s__model_fields' % prefix or 'model_fields'
            field_dict = {'field': field,
                          'name': field_name_prefix,
                          'type': field_type,
                          'verbose_name': field.verbose_name,
                          'help_text': field.help_text}
            if isinstance(field, django_fields.CharField):
                field_dict['choices'] = CHOICES_STR
            elif isinstance(field, django_fields.IntegerField):
                field_dict['choices'] = CHOICES_INTEGER
            elif isinstance(field, django_fields.BooleanField):
                field_dict['choices'] = CHOICES_BOOLEAN
            elif isinstance(field, django_fields.DateField):
                field_dict['choices'] = CHOICES_DATE
            else:
                field_dict['choices'] = CHOICES_ALL
            model_fields.append(field_dict)

    for func_name in dir(model):
        if not callable(getattr(model, func_name, None)):
            continue
        func = getattr(model, func_name)
        if not getattr(func, 'im_func', None):
            continue
        func_num_args = func.im_func.func_code.co_argcount
        func_type = prefix and '%s__func' % prefix or 'func'
        func_name_prefix = func_name
        if prefix:
            func_name_prefix = '%s__%s' % (prefix, func_name)
        if func_num_args == 1 or len(func.im_func.func_dict) == func_num_args:
            funcs.append({'field': func,
                          'name': func_name_prefix,
                          'type': func_type,
                          'verbose_name': func_name,
                          'help_text': func.im_func.func_doc,
                          'choices': None,
                          })
    return (model_fields, objs_related, fields_related, funcs)
