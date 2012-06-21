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

from django.conf import settings
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.admin.views.main import (ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, PAGE_VAR, SEARCH_VAR,
                                             TO_FIELD_VAR, IS_POPUP_VAR, ERROR_FLAG)
from django.contrib.sites.models import Site
from django.db import models
from django.db.models.fields.related import RelatedField
from django.db.models.related import RelatedObject
from django.http import QueryDict
try:
    from django.utils.importlib import import_module
except:
    from importlib import import_module
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import get_language

from autoreports.adaptors import AUTOREPORTS_ADAPTOR as DEFAULT_AUTOREPORTS_ADAPTOR
from autoreports import csv_to_excel

try:
    import transmeta
    IMPORTABLE_TRANSMETA = True
except ImportError:
    IMPORTABLE_TRANSMETA = False


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

EXCLUDE_FIELDS = ('batchadmin_checkbox', 'action_checkbox',
                  ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, PAGE_VAR, SEARCH_VAR,
                  TO_FIELD_VAR, IS_POPUP_VAR, ERROR_FLAG)

SEPARATED_FIELD = "$__$"


def is_iterable(value):
    try:
        import collections
        return isinstance(value, collections.Iterable)
    except (ImportError, AttributeError):
        return getattr(value, '__iter__', False) and True


def add_domain(value):
    site = Site.objects.get_current()
    value = 'http://%s%s' % (site.domain, value)
    return value


def pre_procession_request(request, model, lite=False):

    class RequestFake(object):

        def __init__(self, request, model, lite=False, *args, **kwargs):
            new_get = None
            setattr(self, 'user', getattr(request, 'user', None))
            try:
                path = request.get_full_path()
                path_index = path.index("?")
                new_get = QueryDict(path[path_index + 1:], mutable=True)
                if lite:
                    self.GET = QueryDict("")
                    return
                for key, value in new_get.lists():
                    if not key.startswith('__'):
                        key_with_filter = '__'.join(key.split('__')[:-1])
                        try:
                            model_field, field = get_field_from_model(model, key_with_filter, separated_field='__')
                            adaptor = get_adaptor(field)
                            adaptor = adaptor(model, field, key_with_filter)
                            value, new_get = adaptor.change_value(value, key, new_get)
                            if key in new_get:
                                new_get.setlist(key, value)
                        except models.FieldDoesNotExist:
                            del new_get[key]
                self.GET = new_get
            except ValueError:
                self.GET = QueryDict("")

        def convert_filter_datetime(self, key, endswith, filters, filters_clean):
            key_new = key.replace(endswith, '')
            value_new = '%s %s' % (filters.get('%s_0' % key_new, ''),
                                    filters.get('%s_1' % key_new, ''))
            value_new = value_new.strip()
            return (key_new, value_new)

    if isinstance(request, RequestFake):
        return request

    request_fake = RequestFake(request, model, lite)
    request_fake.get_full_path = request.get_full_path
    if request_fake.GET != request.GET:
        return request_fake
    return request


def get_available_formats():
    formats = {}
    for format, format_data in EXPORT_FORMATS.items():
        if format == 'excel' and not csv_to_excel.HAS_PYEXCELERATOR:
            continue
        formats[format] = format_data
    return formats


def get_ordered_fields(report):
    return sorted(report.options.iteritems(),
                  key=lambda e: len(e) > 0 and e[1].get('order', -1) or -1)


def get_adaptors_from_report(report):
    model = report.content_type.model_class()
    adaptors = []
    if not report.options:
        return adaptors
    report_options_order = get_ordered_fields(report)
    for field_name, ops in report_options_order:
        model_field, field = get_field_from_model(model, field_name)
        adaptors.append(get_adaptor(field)(model, field, field_name, instance=report, treatment_transmeta=False))
    return adaptors


def get_adaptor(field):
    from autoreports.fields import BaseReportField
    adaptor = None
    if isinstance(field, models.CharField) or isinstance(field, models.TextField):
        if getattr(field, 'choices', None):
            adaptor = 'choices'
        else:
            adaptor = 'text'
    elif isinstance(field, models.AutoField):
        adaptor = 'autonumber'
    elif isinstance(field, models.IntegerField) or isinstance(field, models.FloatField):
        adaptor = 'number'
    elif isinstance(field, models.BooleanField):
        adaptor = 'boolean'
    elif isinstance(field, models.DateTimeField):
        adaptor = 'datetime'
    elif isinstance(field, models.DateField):
        adaptor = 'date'
    elif isinstance(field, models.ForeignKey):
        adaptor = 'fk'
    elif isinstance(field, models.ManyToManyField):
        adaptor = 'm2m'
    elif isinstance(field, RelatedObject):
        adaptor = 'relatedreverse'
    elif callable(field):
        adaptor = 'func'
    elif isinstance(field, property):
        adaptor = 'property'
    elif isinstance(field, GenericForeignKey):
        adaptor = 'gfk'
    class_adaptor = adaptor and (get_class_from_path((getattr(settings, 'AUTOREPORTS_ADAPTOR', None) and
                                                     settings.AUTOREPORTS_ADAPTOR.get(adaptor, None)) or
                                                     (DEFAULT_AUTOREPORTS_ADAPTOR.get(adaptor, None))))
    if not class_adaptor:
        return BaseReportField
    return class_adaptor


def get_class_from_path(path):
    if not path:
        return None
    path_module, class_adaptor = ('.'.join(path.split('.')[:-1]), path.split('.')[-1])
    return getattr(import_module(path_module), class_adaptor)


def get_model_of_relation(field):
    if isinstance(field, models.ManyToManyField) or isinstance(field, models.ForeignKey):
        return field.rel.to
    return field.model


def parsed_field_name(field_name, separated_field=SEPARATED_FIELD):
    field_name_list = field_name.split(separated_field)
    field_name = field_name_list[-1]
    prefix = field_name_list[:-1]
    return (prefix, field_name)


def __treatment_to_other_fields(field_name, model_or_api):
    func = getattr(model_or_api, field_name, None)
    if func:
        if callable(func):
            return (field_name, func)
        elif isinstance(func, property):
            return (field_name, func)
        elif isinstance(func, GenericForeignKey):
            return (field_name, func)
    return (field_name, None)


def get_field_by_name(model, field_name, checked_transmeta=True, api=None):
    try:
        return (field_name, model._meta.get_field_by_name(field_name)[0])
    except models.FieldDoesNotExist, e:
        if checked_transmeta and has_transmeta():
            field_name_transmeta = transmeta.get_real_fieldname(field_name, get_language())
            try:
                field_name_transmeta, field = get_field_by_name(model,
                                                                field_name_transmeta,
                                                                checked_transmeta=False)
                return (field_name, field)
            except models.FieldDoesNotExist, e:
                pass
        field_name, func = __treatment_to_other_fields(field_name, model)
        if func:
            return (field_name, func)
        if api:
            field_name, func = __treatment_to_other_fields(field_name, api)
            if func:
                return (field_name, func)
        raise e


def get_value_from_object(obj, field_name, separated_field=SEPARATED_FIELD, api=None):
    if not obj:
        return obj
    if callable(field_name):
        return field_name(obj)
    prefix, field_name_parsed = parsed_field_name(field_name, separated_field)
    model = type(obj)
    if not prefix:
        try:
            field_name, field = get_field_by_name(model, field_name, api=api)
            adaptor = get_adaptor(field)(model, field, field_name)
            return adaptor.get_value(obj, field_name)
        except models.FieldDoesNotExist, e:
            if hasattr(obj, field_name):
                return getattr(obj, field_name, None)
            raise e
    else:
        field_name_current = prefix[0]
        field_name_new = prefix[1:]
        field_name_new.append(field_name_parsed)
        field_name, field = get_field_by_name(model, prefix[0], api=api)
        adaptor = get_adaptor(field)(model, field, field_name)
        value = adaptor.get_value(obj, field_name_current)
        if is_iterable(value):
            value_list = []
            for obj in value:
                val = get_value_from_object(obj,
                                            separated_field.join(field_name_new),
                                            separated_field=separated_field)
                if isinstance(val, basestring):
                    value_list.append(val)
                elif is_iterable(val):
                    value_list.append(val)
                else:
                    value_list.append(val)
            return value_list
        elif isinstance(value, models.Model):
            return get_value_from_object(value,
                                         separated_field.join(field_name_new),
                                         separated_field=separated_field)
        elif value:
            return adaptor.get_value(value, field_name_parsed)


def get_parser_value(value):
    if not value:
        return unicode(value)
    elif isinstance(value, basestring):
        if isinstance(value, str):
            value = unicode(value, 'utf-8')
        return value.encode('utf8')
    elif isinstance(value, models.Model):
        return unicode(value).encode('utf8')
    elif is_iterable(value):
        commas_separated_values = []
        for item in value:
            parsed_val = get_parser_value(item)
            if isinstance(item, basestring):
                commas_separated_values.append(parsed_val)
            elif is_iterable(item):
                commas_separated_values.append("[%s]" % parsed_val)
            else:
                commas_separated_values.append(parsed_val)
        return ', '.join(commas_separated_values)
    return get_parser_value(unicode(value))


def get_field_from_model(model, field_name, separated_field=SEPARATED_FIELD, api=None):
    prefix, field_name_parsed = parsed_field_name(field_name, separated_field)
    if not prefix:
        field_name, field = get_field_by_name(model, field_name,
                                              api=api)
        return (model, field)
    else:
        field_name_new = prefix[1:]
        field_name_new.append(field_name_parsed)
        field_name, field = get_field_by_name(model, prefix[0])
        return get_field_from_model(get_model_of_relation(field),
                                    separated_field.join(field_name_new),
                                    api=api)


def get_all_field_names(model):
    field_list = model._meta.get_all_field_names()
    if has_transmeta():
        field_list = pre_processing_transmeta_fields(model, field_list)
    return field_list


def get_fields_from_model(model, prefix=None, ignore_models=None, adaptors=None):
    fields = []
    funcs = []
    prefix = prefix or ''
    ignore_models = ignore_models or []
    field_list = get_all_field_names(model)
    for field_name in field_list:
        field_name_model, field = get_field_by_name(model, field_name)
        field_name_prefix = prefix and '%s%s%s' % (prefix, SEPARATED_FIELD, field_name) or field_name
        adaptor = get_adaptor(field)(model, field, field_name_prefix)
        if adaptors and not isinstance(adaptor, adaptors):
            continue
        field_data = {'name': field_name,
                      'name_prefix': field_name_prefix}
        if isinstance(field, (RelatedObject, RelatedField)):
            model_relation = get_model_of_relation(field)
            if model_relation in ignore_models:
                continue
            if issubclass(model, model_relation) and field_name.endswith('_ptr'):
                continue
            field_data['verbose_name'] = adaptor.get_verbose_name()
            model_relation = get_model_of_relation(field)
            field_data['collapsible'] = {'app_label': model_relation._meta.app_label,
                                         'module_name': model_relation._meta.module_name}
        else:
            field_data['verbose_name'] = adaptor.get_verbose_name()
            field_data['collapsible'] = False
        fields.append(field_data)

    autoreports_functions = getattr(settings, 'AUTOREPORTS_FUNCTIONS', False)

    if not autoreports_functions or adaptors:
        return (fields, None)

    for func_name in dir(model):
        if not callable(getattr(model, func_name, None)):
            continue
        func = getattr(model, func_name)
        if not getattr(func, 'im_func', None):
            continue
        func_num_args = func.im_func.func_code.co_argcount
        func_name_prefix = func_name
        if prefix:
            func_name_prefix = '%s%s%s' % (prefix, SEPARATED_FIELD, func_name)
        adaptor = get_adaptor(func)(model, func, func_name_prefix)
        if func_num_args == 1 or len(func.im_func.func_dict) == func_num_args:
            funcs.append({'name': func_name_prefix,
                          'verbose_name': adaptor.get_verbose_name(),
                          'collapsible': False
                          })
    return (fields, funcs)


def has_transmeta():
    if IMPORTABLE_TRANSMETA and 'transmeta' in settings.INSTALLED_APPS:
        return True
    return False


def pre_processing_transmeta_fields(model, field_list):
    translatable_fields = transmeta.get_all_translatable_fields(model)
    for translatable_field in translatable_fields:
        fields_to_remove = transmeta.get_real_fieldname_in_each_language(translatable_field)
        for i, field_to_remove in enumerate(fields_to_remove):
            if i == 0:
                index = field_list.index(field_to_remove)
                field_list[index] = translatable_field
            else:
                field_list.remove(field_to_remove)
    return field_list


def filtering_from_request(request, object_list, report=None):
    qsm = get_querystring_manager()(request)
    filters = qsm.get_filters()
    for field in EXCLUDE_FIELDS:
        if field in filters:
            del filters[field]
    if not report or not report.options:
        return (filters, object_list.filter(**filters).distinct())
    else:
        filter_list = {}
        options = report.options
        model = object_list.model
        for fil, value in filters.items():
            fil_split = fil.split('__')
            field_name = SEPARATED_FIELD.join(fil_split[:-1])
            field_name_opts = transmeta_inverse_field_name(model, field_name)
            prefix = '__'.join(fil_split[:-2])
            filter_operator = fil_split[-1]
            field_options = options.get(field_name_opts, None)
            if not field_options or not field_options.get('other_fields', None):
                object_list = object_list.filter(**{fil: value})
                filter_list[fil] = value
            else:
                from django.db.models  import Q
                other_fields = field_options.get('other_fields', None)
                filter_or = Q(**{fil: value})
                filter_list[fil] = [{fil: value}]
                for other_field in other_fields:
                    if prefix:
                        other_field = "%s__%s" % (prefix, other_field)
                    m, f = get_field_from_model(model, other_field, separated_field='__')
                    other_field = transmeta_field_name(f, other_field)
                    other_field = str("%s__%s" % (other_field, filter_operator))
                    filter_or = filter_or | Q(**{other_field: value})
                    filter_list[fil].append({other_field: value})
                object_list = object_list.filter(filter_or)
    return (filter_list, object_list.distinct())


def transmeta_field_name(field, field_name):
    if has_transmeta() and not field_name.endswith(field.name):
        return transmeta.get_real_fieldname(field_name, get_language())
    return field_name


def transmeta_inverse_field_name(model, field_name):
    if has_transmeta():
        lang = get_language()
        field_name_generic = field_name[:-(len(lang) + 1)]
        field_generic = getattr(model, field_name_generic, None)
        if field_generic and isinstance(field_generic, property):
            return field_name_generic
    return field_name


def get_querystring_manager():
    use_cmsutils = getattr(settings, 'AUTOREPORTS_USE_CMSUTILS', True)
    if use_cmsutils:
        from cmsutils.adminfilters import QueryStringManager
    else:
        from autoreports.adminfilters import QueryStringManager
    return QueryStringManager
