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
from django.contrib.admin import ModelAdmin
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.datastructures import SortedDict


from autoreports.forms import ReportFilterForm, ReportDisplayForm
from autoreports.model_forms import modelform_factory
from autoreports.utils import get_available_formats, get_field_from_model, get_adaptor
from autoreports.views import EXCLUDE_FIELDS


class ReportApi(object):

    report_form_filter = ReportFilterForm
    report_form_display = ReportDisplayForm
    report_filter_fields = ()
    report_display_fields = ()
    category = 'no_category'
    category_verbosename = None
    is_admin = False

    EXCLUDE_FIELDS = EXCLUDE_FIELDS

    def __init__(self, model=None, *args, **kwargs):
        if isinstance(self, ModelAdmin):
            super(ReportApi, self).__init__(model, *args, **kwargs)
        else:
            self.model = model
            super(ReportApi, self).__init__(*args, **kwargs)
        self.verbose_name = getattr(self, 'verbose_name', self.__class__.__name__)

    def get_report_form_filter(self, data, fields):
        form_filter_class = modelform_factory(model=self.model,
                                              form=self.report_form_filter)
        form_filter_class.base_fields = fields
        form_filter = form_filter_class(data=data, is_admin=self.is_admin)
        return form_filter

    def get_report_form_display(self, data, fields):
        form_display_class = modelform_factory(model=self.model,
                                               form=self.report_form_display)
        form_display_class.base_fields = fields
        form_display = form_display_class(data=data, is_admin=self.is_admin)
        return form_display

    def get_report(self, request, queryset, form_filter, form_display, submit):
        queryset = queryset or self.model.objects.all()
        return form_filter.get_report(request, queryset, form_display, submit)

    def get_fields_of_form(self, report=None):
        fields_form_filter = SortedDict({})
        fields_form_display = SortedDict({})
        if report and report.options:
            for field_name, opts in report.options.items():
                fields_form_filter, fields_form_display = self.get_field_of_form(field_name, opts,
                                                               fields_form_filter=fields_form_filter,
                                                               fields_form_display=fields_form_display)
        else:
            for field_name in self.get_report_filter_fields():
                fields_form_filter, fields_form_display = self.get_field_of_form(field_name, default=True,
                                                               fields_form_filter=fields_form_filter,
                                                               fields_form_display=fields_form_display)
            for field_name in self.get_report_display_fields():
                fields_form_filter, fields_form_display = self.get_field_of_form(field_name, default=False,
                                                               fields_form_filter=fields_form_filter,
                                                               fields_form_display=fields_form_display)
        return (fields_form_filter, fields_form_display)

    def get_field_of_form(self, field_name, opts=None, default=True,
                                fields_form_filter=None, fields_form_display=None):
        model, field = get_field_from_model(self.model, field_name)
        adaptor = get_adaptor(field)(model, field, field_name)
        return adaptor.get_field_form(opts, default, fields_form_filter, fields_form_display)

    def get_django_query(self, _adavanced_filters):
        model_name = self.model.__name__
        query = 'from %s import %s' % (self.model.__module__, model_name)
        query += '\n%s.objects.filter(**%s).distinct()' % (model_name, unicode(_adavanced_filters))
        return query

    def report(self, request, report=None, queryset=None, template_name='autoreports/autoreports_form.html', extra_context=None):
        export_report = (request.GET.get('__report_csv', None) and 'csv') or (request.GET.get('__report_excel', None) and 'excel')
        data = request.GET or None
        fields_form_filter, fields_form_display = self.get_fields_of_form(report)
        form_filter = self.get_report_form_filter(data, fields_form_filter)
        form_display = self.get_report_form_display(data, fields_form_display)
        are_valid = False
        if data:
            are_valid = form_display.is_valid() and form_filter.is_valid()
        if export_report and are_valid:
            return self.get_report(request, queryset, form_filter, form_display, export_report)
        extra_context = extra_context or {}
        _adavanced_filters = extra_context.get('_adavanced_filters', None)
        django_query = None
        if are_valid and _adavanced_filters:
            django_query = self.get_django_query(_adavanced_filters)
        context = {'form_filter': form_filter,
                   'form_display': form_display,
                   'template_base': getattr(settings, 'AUTOREPORTS_BASE_TEMPLATE', 'base.html'),
                   'export_formats': get_available_formats(),
                   'api': self,
                   'ADMIN_MEDIA_PREFIX': settings.ADMIN_MEDIA_PREFIX,
                   'report': report,
                   'django_query': django_query,
                  }
        context.update(extra_context)
        return render_to_response(template_name,
                                 context,
                                 context_instance=RequestContext(request))

    def get_report_filter_fields(self):
        report_filter_fields = self.report_filter_fields or getattr(self, 'list_display', tuple())
        set_fields = [report_filter_field for report_filter_field in report_filter_fields if report_filter_field not in self.EXCLUDE_FIELDS]
        report_filter_fields = list(set_fields)
        return report_filter_fields

    def get_report_display_fields(self):
        report_display_fields = self.report_display_fields or getattr(self, 'list_display', ('__unicode__', ))
        set_fields = [report_display_field for report_display_field in report_display_fields if report_display_field not in self.EXCLUDE_FIELDS]
        report_display_fields = list(set_fields)
        return report_display_fields
