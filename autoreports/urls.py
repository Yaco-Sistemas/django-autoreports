from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('autoreports.views',
    url(r'^(?P<app_name>[\w-]+)/(?P<model_name>[\w-]+)/$', 'reports_view', name='reports_view'),
    url(r'^(?P<app_name>[\w-]+)/(?P<model_name>[\w-]+)/(?P<model_admin_module>[\.\w-]+)/(?P<model_admin_class_name>[\w-]+)/$', 'model_admin_reports_view', name='model_admin_reports_view'),
    )
