from django.contrib.admin.util import unquote

from autoreports.api import ReportApi


class ReportAdmin(ReportApi):

    is_admin = True

    def __call__(self, request, url):
        if url and url.endswith('report'):
            url = url[:url.find('/report')]
            return self.report(request)
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
                wrap(self.report),
                name='%s_%s_report' % info),
        ) + urlpatterns
        return urlpatterns

    def report(self, request, queryset=None, template_name='autoreports/autoreports_adminform.html', extra_context=None):
        context = {'opts': self.opts,
                   'template_base': "admin/base_site.html",
                    }
        extra_context = extra_context or {}
        context.update(extra_context)
        return super(ReportAdmin, self).report(request, self.queryset(request), template_name, context)
