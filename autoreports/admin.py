import re

from django import template
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.util import unquote
from django.contrib.admin.views.main import ChangeList, ERROR_FLAG
from django.contrib.admin.templatetags.admin_list import result_headers
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils import simplejson
from django.utils.translation import ugettext_lazy as _

from autoreports.api import ReportApi
from autoreports.forms import ReportNameAdminForm, ReportNameForm
from autoreports.models import Report
from autoreports.utils import get_fields_from_model
from autoreports.views import reports_view, set_filters_search_fields


class ReportAdmin(ReportApi):

    is_admin = True

    def __call__(self, request, url):
        if url and url.endswith('report'):
            url = url[:url.find('/report/')]
            return self.report_list(request)
        elif url and url.endswith('report/wizard'):
            url = url[:url.find('/report/wizard')]
            return self.report_wizard(request)
        elif url and url.endswith('report/advance'):
            url = url[:url.find('/report/advance')]
            return self.report_advance(request)
        elif url and url.endswith('report/quick'):
            url = url[:url.find('/report/quick')]
            return self.report_quick(request)
        elif url:
            url_compile = re.compile('.*report/(?P<report_id>\d+)$')
            m = url_compile.match(url)
            if m:
                report_id = m.groupdict()['report_id']
                return self.report_view(request, report_id)
        return super(ReportAdmin, self).__call__(request, url and unquote(url) or url)

    def get_urls(self):
        from django.conf.urls.defaults import patterns, url
        from django.utils.functional import update_wrapper

        def wrap(view):

            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        urlpatterns = super(ReportAdmin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.module_name

        urlpatterns = patterns('',
                url(r'^report/$',
                      wrap(self.report_list),
                      name='%s_%s_report_list' % info),
                url(r'^report/wizard/$',
                      wrap(self.report_wizard),
                      name='%s_%s_report_wizard' % info),
                url(r'^report/advance/$',
                      wrap(self.report_advance),
                      name='%s_%s_report_advance' % info),
                url(r'^report/quick/$',
                      wrap(self.report_quick),
                      name='%s_%s_report_quick' % info),
                url(r'^report/(?P<report_id>\d+)/$',
                      wrap(self.report_view),
                      name='%s_%s_report_view' % info),
        ) + urlpatterns
        return urlpatterns

    def report_list(self, request, extra_context=None):
        "The 'change list' admin view for this model."
        model = Report
        opts = model._meta
        app_label = opts.app_label

        try:
            list_display = ('name', )
            list_display_links = tuple()
            list_filter = tuple()
            date_hierarchy = None
            search_fields = tuple()
            list_select_related = False
            list_per_page = 100
            try:
                cl = ChangeList(request, Report, list_display, list_display_links, list_filter,
                    date_hierarchy, search_fields, list_select_related, list_per_page, admin.site._registry[model])
            except TypeError:
                cl = ChangeList(request, Report, list_display, list_display_links, list_filter,
                    date_hierarchy, search_fields, list_select_related, list_per_page, (), admin.site._registry[model])
                cl.formset = None
        except IncorrectLookupParameters:
            # Wacky lookup parameters were given, so redirect to the main
            # changelist page, without parameters, and pass an 'invalid=1'
            # parameter via the query string. If wacky parameters were given and
            # the 'invalid=1' parameter was already in the query string, something
            # is screwed up with the database, so display an error page.
            if ERROR_FLAG in request.GET.keys():
                return render_to_response('admin/invalid_setup.html', {'title': _('Database error')})
            return HttpResponseRedirect(request.path + '?' + ERROR_FLAG + '=1')

        content_type = ContentType.objects.get_for_model(self.model)
        cl.query_set = cl.query_set.filter(content_type=content_type)
        cl.result_list = cl.query_set._clone()
        context = {
            'title': cl.title,
            'is_popup': cl.is_popup,
            'cl': cl,
            'has_add_permission': False,
            'root_path': self.admin_site.root_path,
            'app_label': app_label,
            'opts': self.opts,
        }
        context.update(extra_context or {})
        return render_to_response(getattr(self, 'change_report_list_template', None) or [
            'autoreports/%s/%s/report_adminlist.html' % (app_label, opts.object_name.lower()),
            'autoreports/%s/report_adminlist.html' % app_label,
            'autoreports/report_adminlist.html',
        ], context, context_instance=template.RequestContext(request))

    def report_wizard(self, request, queryset=None, template_name='autoreports/autoreports_adminwizard.html', extra_context=None):
        content_type = ContentType.objects.get_for_model(self.model)
        return self.report_api_wizard(request, queryset=queryset,
                                      template_name=template_name,
                                      extra_context=extra_context,
                                      model=Report,
                                      form_top_class=ReportNameAdminForm,
                                      content_type=content_type)

    def report_api_wizard(self, request,
                          queryset=None, template_name='autoreports/autoreports_adminwizard.html',
                          extra_context=None,
                          model_to_report=None,
                          model=Report,
                          form_top_class=ReportNameForm,
                          content_type=None):
        data = None
        if request.method == 'POST':
            data = request.POST
        form_top = form_top_class(data=data)
        if form_top.is_valid():
            report_filter_fields = []
            report_display_fields = []
            report_advance = {}
            for check, value in request.POST.items():
                if check.startswith('display_'):
                    report_display_fields.append(check.replace('display_', ''))
                elif check.startswith('filter_'):
                    report_filter_fields.append(check.replace('filter_', ''))
                elif check.startswith('widget_'):
                    field_name = check.replace('widget_', '')
                    report_advance[field_name] = {'widget': value}
                    default_value = request.POST.get(field_name, None)
                    if default_value:
                        report_advance[field_name]['default'] = default_value
            name = form_top.cleaned_data.get('name', None) or 'report of %s' % unicode(self.model._meta.verbose_name)
            report = self._create_report(model, name, report_display_fields,
                                        report_filter_fields, content_type,
                                        report_advance)
            return HttpResponseRedirect('../%s' % report.id)
        model_fields, objs_related, fields_related, funcs = get_fields_from_model(content_type.model_class())
        context = {'add': True,
                   'opts': self.opts,
                   'model_fields': model_fields,
                   'fields_related': fields_related,
                   'objs_related': objs_related,
                   'funcs': funcs,
                   'columns': model.get_colums_wizard(),
                   'ADMIN_MEDIA_PREFIX': settings.ADMIN_MEDIA_PREFIX,
                   'template_base': "admin/base_site.html",
                   'level_margin': 0,
                   'form_top': form_top,
                   'module_name': content_type.model,
                   'app_label': content_type.app_label,
                   'model__module_name': model._meta.module_name,
                   'model__app_label': model._meta.app_label,
                  }
        extra_context = extra_context or {}
        context.update(extra_context)
        return render_to_response(template_name,
                                  context,
                                  context_instance=RequestContext(request))

    def _create_report(self, model, name, report_display_fields, report_filter_fields, content_type, report_advance):
        report = model.objects.create(name=name,
                                      report_display_fields=', '.join(report_display_fields),
                                      report_filter_fields=', '.join(report_filter_fields),
                                      content_type=content_type,
                                      advanced_options=simplejson.dumps(report_advance))
        return report

    def report_view(self, request, report_id, queryset=None, template_name='autoreports/autoreports_adminform.html', extra_context=None):
        report = Report.objects.get(pk=report_id)
        return self.report_advance(request, report=report, queryset=queryset, template_name=template_name, extra_context=extra_context)

    def report_advance(self, request, report=None, queryset=None, template_name='autoreports/autoreports_adminform.html', extra_context=None):
        context = {'opts': self.opts,
                   'template_base': "admin/base_site.html",
                    }
        extra_context = extra_context or {}
        context.update(extra_context)
        return super(ReportAdmin, self).report(request, report, self.queryset(request), template_name, context)

    def report_quick(self, request):
        fields = list(getattr(self, 'list_display', ('__unicode__', )))
        filters = Q()
        ordering = self.ordering
        if request.GET.get('q', None):
            filters = set_filters_search_fields(self, request, filters, self.model)
        if request.GET.get('o', None):
            ordering = list(fields)[int(request.GET.get('o', None))]
            if request.GET.get('ot', None) and request.GET.get('ot') == 'desc':
                ordering = '-%s' % ordering
            ordering = (ordering, )
        queryset = self.queryset(request)

        try:
            try:
                cl = ChangeList(request, self.model, self.list_display, self.list_display_links, self.list_filter,
                    self.date_hierarchy, self.search_fields, self.list_select_related, self.list_per_page, self)
            except TypeError:
                cl = ChangeList(request, self.model, self.list_display, self.list_display_links, self.list_filter,
                    self.date_hierarchy, self.search_fields, self.list_select_related, self.list_per_page, self.list_editable, self)
            headers = list(result_headers(cl))
            j = 0
            for i, header in enumerate(headers):
                if not header.get('url', None) and not getattr(self.model, fields[i-j], None):
                    del fields[i-j]
                    j = j + 1
        except IncorrectLookupParameters:
            pass

        return reports_view(request, self.model._meta.app_label, self.model._meta.module_name,
                            fields=fields, list_headers=None, ordering=ordering, filters=filters,
                            model_admin=self, queryset=queryset,
                            report_to='csv')
