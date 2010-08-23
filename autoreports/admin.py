from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.util import unquote
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.templatetags.admin_list import result_headers
from django.db.models import Q

from autoreports.api import ReportApi
from autoreports.views import reports_view, set_filters_search_fields


class ReportAdmin(ReportApi):

    is_admin = True

    def __call__(self, request, url):
        if url and url.endswith('report/advance'):
            url = url[:url.find('/report/advance')]
            return self.report_advance(request)
        elif url and url.endswith('report/quick'):
            url = url[:url.find('/report/quick')]
            return self.report_quick(request)
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
            url(r'^report/advance/$',
                wrap(self.report_advance),
                name='%s_%s_report_advance' % info),
            url(r'^report/quick/',
                wrap(self.report_quick),
                name='%s_%s_report_quick' % info),
        ) + urlpatterns
        return urlpatterns

    def report_advance(self, request, queryset=None, template_name='autoreports/autoreports_adminform.html', extra_context=None):
        context = {'opts': self.opts,
                   'template_base': "admin/base_site.html",
                    }
        extra_context = extra_context or {}
        context.update(extra_context)
        return super(ReportAdmin, self).report(request, self.queryset(request), template_name, context)

    def report_quick(self, request):
        fields = list(getattr(self, 'list_display', ('__unicode__', )))
        try:
            try:
                cl = ChangeList(request, self.model, self.list_display, self.list_display_links, self.list_filter,
                    self.date_hierarchy, self.search_fields, self.list_select_related, self.list_per_page, self)
            except TypeError:
                cl = ChangeList(request, self.model, self.list_display, self.list_display_links, self.list_filter,
                    self.date_hierarchy, self.search_fields, self.list_select_related, self.list_per_page, self.list_editable, self)
            headers = list(result_headers(cl))
            for i, header in enumerate(headers):
                if not header.get('url', None):
                    del fields[i]
        except IncorrectLookupParameters:
            pass
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
        return reports_view(request, self.model._meta.app_label, self.model._meta.module_name,
                            fields=fields, list_headers=None, ordering=ordering, filters=filters,
                            model_admin=self, queryset=queryset,
                            report_to='csv')
