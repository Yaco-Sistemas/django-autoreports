from django.contrib import admin
from django.contrib.admin.util import unquote
from django.forms.models import modelform_factory
from django.shortcuts import render_to_response
from django.template import RequestContext

from autoreports.forms import ReportForm


class ReportAdmin(admin.ModelAdmin):

    report_form = ReportForm

    def report(self, request):
        form_class = modelform_factory(model=self.model,
                          form=self.report_form)
        form = form_class(fields=self.get_report_fields())
        if request.GET.get('__report', None):
            queryset = self.queryset(request)
            return form.get_report(request, queryset)
        return render_to_response('autoreports/autoreports_form.html', {'form': form},
                        context_instance=RequestContext(request))

    def __call__(self, request, url):
        if url and url.endswith('report'):
            url = url[:url.find('/report')]
            return self.report(request)
        return super(ReportAdmin, self).__call__(request, url and unquote(url) or url)

    def get_report_fields(self):
        return self.report_fields
