from django.conf import settings
from django.contrib.admin import ModelAdmin
from django.shortcuts import render_to_response
from django.template import RequestContext

from autoreports.forms import ReportFilterForm, ReportDisplayForm
from autoreports.models import modelform_factory
from autoreports.utils import get_available_formats
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

    def get_report_form_filter(self, data, report=None):
        form_filter_class = modelform_factory(model=self.model,
                          form=self.report_form_filter)
        form_filter = form_filter_class(data=data, fields=self.get_report_filter_fields(report), is_admin=self.is_admin, report=report)

        return form_filter

    def get_report_form_display(self, data, report=None):
        form_display_class = modelform_factory(model=self.model,
                          form=self.report_form_display)
        form_display = form_display_class(data=data, fields=self.get_report_display_fields(report), is_admin=self.is_admin, report=report)
        return form_display

    def report(self, request, report=None, queryset=None, template_name='autoreports/autoreports_form.html', extra_context=None):
        submit = (request.GET.get('__report_csv', None) and 'csv') or (request.GET.get('__report_excel', None) and 'excel')
        data = submit and request.GET or None
        form_filter = self.get_report_form_filter(data, report)
        form_display = self.get_report_form_display(data, report)
        if data and form_display.is_valid() and form_filter.is_valid():
            report_display_fields = form_display.cleaned_data.get('__report_display_fields_choices', [])
            queryset = queryset or self.model.objects.all()

            return form_filter.get_report(request, queryset, report_display_fields, submit)
        extra_context = extra_context or {}
        context = {'form_filter': form_filter,
                   'form_display': form_display,
                   'template_base': getattr(settings, 'AUTOREPORTS_BASE_TEMPLATE', 'base.html'),
                   'export_formats': get_available_formats(),
                   'api': self,
                   'ADMIN_MEDIA_PREFIX': settings.ADMIN_MEDIA_PREFIX,
                   'report': report,
                  }
        context.update(extra_context)
        return render_to_response(template_name,
                                 context,
                                 context_instance=RequestContext(request))

    def get_report_filter_fields(self, report=None):
        if report:
            return report.report_filter_fields_tuple
        report_filter_fields = self.report_filter_fields or getattr(self, 'list_display', tuple())
        set_fields = [report_filter_field for report_filter_field in report_filter_fields if report_filter_field not in self.EXCLUDE_FIELDS]
        report_filter_fields = list(set_fields)
        return report_filter_fields

    def get_report_display_fields(self, report=None):
        if report:
            return report.report_display_fields_tuple
        report_display_fields = self.report_display_fields or getattr(self, 'list_display', ('__unicode__', ))
        set_fields = [report_display_field for report_display_field in report_display_fields if report_display_field not in self.EXCLUDE_FIELDS]
        report_display_fields = list(set_fields)
        return report_display_fields
