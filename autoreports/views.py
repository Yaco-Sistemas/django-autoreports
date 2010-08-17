import csv
import locale

from copy import copy

from django.conf import settings
from django.contrib.admin import site
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.utils.translation import get_language

from decimal import Decimal
from cmsutils.adminfilters import QueryStringManager

from autoreports.utils import add_domain
from autoreports.csv_to_excel import  convert_to_excel

CHANGE_VALUE = {'get_absolute_url': add_domain}
EXCLUDE_FIELDS = ('batchadmin_checkbox', 'action_checkbox')
EXTENSION_FILE = {'csv': 'csv',
                  'excel': 'xls'}


def reports_list(request, category_key=None):
    from autoreports.registry import report_registry
    reports_registry = report_registry.get_registered_for_category(category_key)
    return render_to_response('autoreports/autoreports_list.html',
                              {'reports_registry': reports_registry,
                               'template_base': getattr(settings, 'AUTOREPORTS_BASE_TEMPLATE', 'base.html'),
                              },
                              context_instance=RequestContext(request))


def reports_api(request, registry_key):
    from autoreports.registry import report_registry
    api = report_registry.get_api_class(registry_key)
    return api.report(request)


def reports_view(request, app_name, model_name, fields=None,
                 list_headers=None, ordering=None, filters=Q(),
                 model_admin=None, queryset=None,
                 report_to='csv'):
    request_get = request.GET.copy()

    class_model = models.get_model(app_name, model_name)
    list_fields = fields

    if not list_fields:
        model_admin = model_admin or site._registry.get(class_model, None)
        if model_admin:
            list_fields = model_admin.list_display
            set_fields = set(list_fields) - set(EXCLUDE_FIELDS)
            list_fields = list(set_fields)
        else:
            list_fields = ['__unicode__']
            list_headers = [_('Object')]

    list_headers = list_headers
    if not list_headers:
        list_headers = translate_fields(list_fields, class_model)
    name = "%s-%s.%s" %(app_name, model_name, EXTENSION_FILE[report_to])

    qsm = QueryStringManager(request)
    object_list = queryset and queryset.filter(filters) or class_model.objects.filter(filters)
    filters = qsm.get_filters()
    filters_clean = {}

    def convert_filter_datetime(key, endswith, filters, filters_clean):
        keys_endswith = {'__lte_0': '__lte',
                         '__gte_0': '__gte',
                         '__lte_1': '__lte',
                         '__gte_1': '__gte'}
        key_new = key.replace(endswith, keys_endswith[endswith])
        value_new = '%s %s' %(filters.get('%s_0' % key_new, ''),
                                filters.get('%s_1' % key_new, ''))
        value_new = value_new.strip()
        if value_new:
            filters_clean[key_new] = value_new

    for key, value in filters.items():
        if value == [u'']:
            continue
        elif value == '' and (key.endswith('__lte') or key.endswith('__gte')):
            continue
        elif key.endswith('__lte_0'):
            convert_filter_datetime(key, '__lte_0', filters, filters_clean)
        elif key.endswith('__gte_0'):
            convert_filter_datetime(key, '__gte_0', filters, filters_clean)
        elif key.endswith('__lte_1'):
            convert_filter_datetime(key, '__lte_1', filters, filters_clean)
        elif key.endswith('__gte_1'):
            convert_filter_datetime(key, '__gte_1', filters, filters_clean)
        else:
            filters_clean[key] = filters[key]

    object_list = object_list.filter(**filters_clean)
    if ordering:
        object_list = object_list.order_by(ordering)

    response = csv_head(request, name, list_headers)
    csv_body(response, class_model, object_list, list_fields)
    if report_to == 'excel':
        convert_to_excel(response)
    return response


def model_admin_reports_view(request, app_name, model_name, model_admin_module,
                             model_admin_class_name, fields=None, list_headers=None,
                             ordering=None, filters=Q()):
    model_admin = getattr(__import__(model_admin_module, {}, {}, model_admin_class_name), model_admin_class_name)
    fields = fields or getattr(model_admin, 'report_display_fields', None) or getattr(model_admin, 'list_display', None)
    if request.GET.get('q', None):
        request = copy(request)
        class_model = ContentType.objects.get(app_label=app_name, model=model_name).model_class()
        filters = set_filters_search_fields(model_admin, request, filters, class_model)
    return reports_view(request, app_name, model_name, fields=fields,
                        list_headers=list_headers, ordering=ordering,
                        model_admin=model_admin, filters=filters)


def set_filters_search_fields(model_admin, request, filters, class_model):
    query = request.GET.get('q', '')
    lang = get_language()
    for field_name in model_admin.search_fields:
        if (field_name, class_model) and is_translate_field(field_name, class_model):
            field_name = '%s_%s' %(field_name, lang)
        filters = filters | Q(**{'%s__icontains' % field_name: query})
    del request.GET['q']
    return filters


def translate_fields(list_fields, class_model):
    list_translate = []
    lang = get_language()
    for field_name in list_fields:
        try:
            if is_translate_field(field_name, class_model):
                field_name = '%s_%s' %(field_name, lang)
            field = class_model._meta.get_field_by_name(field_name)
            field_unicode = unicode(field[0].verbose_name)
        except models.fields.FieldDoesNotExist:
            field_unicode = field_name
        list_translate.append(field_unicode.encode('utf8'))
    return list_translate


def is_translate_field(field_name, class_model):
    if field_name in getattr(class_model._meta, 'translatable_fields', []):
        return True
    for class_parent in class_model._meta.parents.keys():
        if field_name in getattr(class_parent._meta, 'translatable_fields', []):
            return True
    return False


def csv_head(request, filename, columns, delimiter=','):
    response = HttpResponse(mimetype='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=%s' %filename
    writer = csv.writer(response, delimiter=delimiter)
    writer.writerow(columns)
    return response


def get_row_and_field_name(row, field_name):
    if '__' not in field_name or (getattr(row, field_name, None) and callable(getattr(row, field_name))):
        return [(row, field_name)]
    field_split = field_name.split('__')
    row = getattr(row, field_split[0])
    if getattr(row, 'all', None):
        row = row.all()
    if not row:
        return [(None, field_name)]
    field_name = '__'.join(field_split[1:])
    try:
        iter(row)
        row_field_name = []
        for r in row:
            row_field_name.extend(get_row_and_field_name(r, field_name))
        return row_field_name
    except TypeError:
        return get_row_and_field_name(row, field_name)


def csv_body(response, class_model, object_list, list_fields, delimiter=','):
    writer = csv.writer(response, delimiter=delimiter)
    try:
        oldlocale = locale.setlocale(locale.LC_ALL, 'es_ES.UTF8')
    except locale.Error:
        oldlocale = locale.setlocale(locale.LC_ALL, 'es_ES')
    lang = get_language()
    for row_old in object_list:
        values = []
        for field_name in list_fields:
            row_field_name = get_row_and_field_name(row_old, field_name)
            value = get_value(row_field_name, class_model, lang)
            values.append(value)
        writer.writerow(values)
    value = response.content
    value = value.replace('\t', ' ').replace('\r\n', '\n')
    value = value.replace('\n\n', '\n')
    response.content = value
    locale.setlocale(locale.LC_ALL, oldlocale)


def get_value(row_field_name, class_model, lang):
    v = ''
    for row, field_name in row_field_name:
        if row and hasattr(row, field_name):
            try:
                if is_translate_field(field_name, class_model):
                    field_name = '%s_%s' %(field_name, lang)
                field = class_model._meta.get_field(field_name)
            except models.FieldDoesNotExist:
                field = None
            if isinstance(field, models.ForeignKey) and isinstance(getattr(row, field_name, None), int):
                name_aplication = field.rel.to._meta.app_label
                model_foreing = field.rel.to._meta.module_name
                class_model_foreing=models.get_model(name_aplication, model_foreing)
                value = class_model_foreing.objects.get(id=row.id)
            elif getattr(field, 'choices', None):
                value = getattr(row, field_name)
                choices_dict = dict(field.choices)
                value = unicode(choices_dict.get(value, value))
            else:
                value = getattr(row, field_name)
                if hasattr(value, '__call__'):
                    value = value()
                elif getattr(value, 'all', None):
                    value = ', '.join([val.__unicode__() for val in value.all()])
            if isinstance(value, unicode):
                value = value.encode('utf8')
            if isinstance(value, str):
                while value.endswith('\n'):
                    value = value[:-1]
            elif isinstance(value, (float, Decimal)):
                value = locale.format('%.3f', value)
        else:
            value = ''
        if field_name in CHANGE_VALUE:
            value = CHANGE_VALUE[field_name](value)
        if v:
            v = '%s, %s' %(v, value)
        elif isinstance(value, models.Model):
            v = unicode(value).encode('utf-8')
        else:
            v = value
    return v
