 # Copyright (c) 2010 by Yaco Sistemas <pmartin@yaco.es>
 #
 # This program is free software: you can redistribute it and/or modify
 # it under the terms of the GNU Lesser General Public License as published by
 # the Free Software Foundation, either version 3 of the License, or
 # (at your option) any later version.
 #
 # This program is distributed in the hope that it will be useful,
 # but WITHOUT ANY WARRANTY; without even the implied warranty of
 # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 # GNU Lesser General Public License for more details.
 #
 # You should have received a copy of the GNU Lesser General Public License
 # along with this programe.  If not, see <http://www.gnu.org/licenses/>.

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
               ('iexact', ugettext('exact')),
               ('id__in', ugettext('exact related')), )


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


def change_widget(widget_selected, field):
    widget_class = getattr(__import__('django.forms.widgets', {}, {}, True), widget_selected, None)
    widget_dict = field.widget.__dict__
    choices = getattr(field.widget, 'choices', None)
    field.widget = widget_class()
    field.widget.choices = choices
    field.widget.__dict__ = widget_dict
    return field


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

        if field_name.endswith('_ptr'):
            continue
        elif isinstance(field, RelatedObject):
            #import ipdb; ipdb.set_trace()
            field_type = prefix and '%s__objs_related' % prefix or 'objs_related'
            objs_related.append({'field': field,
                                 'name': field_name_prefix,
                                 'choices': CHOICES_RELATED,
                                 'type': field_type,
                                 'verbose_name': field_name,
                                 'app_label': field.model._meta.app_label,
                                 'module_name': field.model._meta.module_name,
                                 'help_text': '',
                                 'advanced_options': True, })
        elif isinstance(field, RelatedField):
            field_type = prefix and '%s__fields_related' % prefix or 'fields_related'
            fields_related.append({'field': field,
                                  'name': field_name_prefix,
                                  'choices': CHOICES_RELATED,
                                  'type': field_type,
                                  'verbose_name': field.verbose_name,
                                  'app_label': field.rel.to._meta.app_label,
                                  'module_name': field.rel.to._meta.module_name,
                                  'help_text': field.help_text,
                                  'advanced_options': True, })
        else:
            field_type = prefix and '%s__model_fields' % prefix or 'model_fields'
            field_dict = {'field': field,
                          'name': field_name_prefix,
                          'type': field_type,
                          'verbose_name': field.verbose_name,
                          'help_text': field.help_text,
                          'advanced_options': True, }
            if isinstance(field, django_fields.CharField) or isinstance(field, django_fields.TextField):
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
                          'advanced_options': False,
                          })
    return (model_fields, objs_related, fields_related, funcs)
