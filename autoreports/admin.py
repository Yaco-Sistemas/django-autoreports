from django.contrib import admin
from django.contrib.admin.util import unquote
from django.forms.models import modelform_factory
from django.shortcuts import render_to_response
from django.template import RequestContext

from autoreports.forms import ReportFilterForm
from autoreports.forms import ReportDisplayForm
from autoreports.views import EXCLUDE_FIELDS


class ReportAdmin(admin.ModelAdmin):

    report_form_filter = ReportFilterForm
    report_form_display = ReportDisplayForm
    report_filter_fields = ()
    report_display_fields = ()

    def get_report_form_filter(self):
        form_filter_class = modelform_factory(model=self.model,
                          form=self.report_form_filter)
        form_filter = form_filter_class(fields=self.get_report_filter_fields())

        return form_filter

    def get_report_form_display(self, data):
        form_display_class = modelform_factory(model=self.model,
                          form=self.report_form_display)
        form_display = form_display_class(data=data, fields=self.get_report_display_fields())

        return form_display

    def report(self, request):
        data = request.GET.get('__report', None) and request.GET or None

        form_filter = self.get_report_form_filter()
        form_display = self.get_report_form_display(data)

        if data and form_display.is_valid():
            report_display_fields = form_display.cleaned_data['__report_display_fields_choices']
            queryset = self.queryset(request)
            return form_filter.get_report(request, queryset, report_display_fields)
        return render_to_response('autoreports/autoreports_form.html',
                                 {
                                  'form_filter': form_filter,
                                  'form_display': form_display,
                                  'opts': self.opts,
                                    },
                                 context_instance=RequestContext(request))

    def __call__(self, request, url):
        if url and url.endswith('report'):
            url = url[:url.find('/report')]
            return self.report(request)
        return super(ReportAdmin, self).__call__(request, url and unquote(url) or url)

    def get_report_filter_fields(self):
        report_filter_fields = self.report_filter_fields or self.list_display
        set_fields = [report_filter_field for report_filter_field in report_filter_fields if report_filter_field not in EXCLUDE_FIELDS]
        report_filter_fields = list(set_fields)
        return report_filter_fields

    def get_report_display_fields(self):
        report_display_fields = self.report_display_fields or self.list_display
        set_fields = [report_display_field for report_display_field in report_display_fields if report_display_field not in EXCLUDE_FIELDS]
        report_display_fields = list(set_fields)
        return report_display_fields
