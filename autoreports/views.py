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

import csv
import locale

from django.conf import settings
from django.contrib.admin import site
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from django.utils.translation import get_language

from cmsutils.adminfilters import QueryStringManager

from autoreports.utils import (EXCLUDE_FIELDS,
                               get_available_formats,
                               get_fields_from_model,
                               get_value_from_object,
                               get_parser_value,
                               get_adaptor, parsed_field_name,
                               get_field_by_name, pre_procession_request)
from autoreports.csv_to_excel import  convert_to_excel


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


def reports_ajax_fields(request):
    module_name = request.GET.get('module_name')
    app_label = request.GET.get('app_label')
    ct = ContentType.objects.get(model=module_name,
                                 app_label=app_label)
    field = request.GET.get('field')
    model = ct.model_class()
    fields, funcs = get_fields_from_model(model, field)
    context = {'fields': fields,
               'funcs': funcs,
               'app_label': app_label,
               'module_name': module_name}
    return HttpResponse(render_to_string('autoreports/inc.render_model.html',
                                         context),
                        mimetype='text/html')


def reports_ajax_fields_options(request):
    module_name = request.GET.get('module_name')
    app_label = request.GET.get('app_label')
    is_admin = request.GET.get('is_admin')
    ct = ContentType.objects.get(model=module_name,
                                 app_label=app_label)
    model = ct.model_class()
    field_name = request.GET.get('field')
    prefix, field_name_parsed = parsed_field_name(field_name)
    field_name_x, field = get_field_by_name(model, field_name_parsed)
    adaptor = get_adaptor(field)(model, field, field_name)
    wizard = adaptor.get_form(is_admin)
    wizard_render = adaptor.render(wizard, model, is_admin)
    return HttpResponse(wizard_render,
                        mimetype='text/html')


def reports_view(request, app_name, model_name, fields=None,
                 list_headers=None, ordering=None, filters=Q(),
                 model_admin=None, queryset=None,
                 report_to='csv'):
    class_model = models.get_model(app_name, model_name)
    request = pre_procession_request(request, class_model)
    list_fields = fields
    formats = get_available_formats()

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
    name = "%s-%s.%s" % (app_name, model_name, formats[report_to]['file_extension'])

    qsm = QueryStringManager(request)
    object_list = queryset and queryset.filter(filters) or class_model.objects.filter(filters)

    filters = qsm.get_filters()

    for field in EXCLUDE_FIELDS:
        if field in filters:
            del filters[field]

    object_list = object_list.filter(**filters).distinct()
    if ordering:
        object_list = object_list.order_by(*ordering)

    response = csv_head(name, list_headers)
    csv_body(response, class_model, object_list, list_fields)
    if report_to == 'excel':
        convert_to_excel(response)
    return response


def set_filters_search_fields(model_admin, request, filters, class_model):
    query = request.GET.get('q', '')
    lang = get_language()
    for field_name in model_admin.search_fields:
        if (field_name, class_model) and is_translate_field(field_name, class_model):
            field_name = '%s_%s' % (field_name, lang)
        filters = filters | Q(**{'%s__icontains' % field_name: query})
    return filters


def translate_fields(list_fields, class_model):
    list_translate = []
    lang = get_language()
    for field_name in list_fields:
        try:
            if is_translate_field(field_name, class_model):
                field_name = '%s_%s' % (field_name, lang)
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


def csv_head(filename, columns, delimiter=','):
    response = HttpResponse(mimetype='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    writer = csv.writer(response, delimiter=delimiter)
    writer.writerow(columns)
    return response


def csv_body(response, class_model, object_list, list_fields, delimiter=','):
    writer = csv.writer(response, delimiter=delimiter)
    try:
        oldlocale = locale.setlocale(locale.LC_ALL, 'es_ES.UTF8')
    except locale.Error:
        oldlocale = locale.setlocale(locale.LC_ALL, 'es_ES')
    for obj in object_list:
        values = []
        for field_name in list_fields:
            value = get_value_from_object(obj, field_name)
            value = get_parser_value(value)
            values.append(value)
        writer.writerow(values)
    value = response.content
    value = value.replace('\t', ' ').replace('\r\n', '\n')
    value = value.replace('\n\n', '\n')
    response.content = value
    locale.setlocale(locale.LC_ALL, oldlocale)
