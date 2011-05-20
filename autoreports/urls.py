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

from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('autoreports.views',
    url(r'^ajax/fields/tree/$', 'reports_ajax_fields', name='reports_ajax_fields'),
    url(r'^ajax/fields/options/$', 'reports_ajax_fields_options', name='reports_ajax_fields_options'),


    url(r'^(category/(?P<category_key>[\w-]+)/)?$', 'reports_list', name='reports_list'),
    url(r'^(?P<registry_key>[\w-]+)/$', 'reports_api', name='reports_api'),
    url(r'^(?P<registry_key>[\w-]+)/wizard/$', 'reports_api_wizard', name='reports_api_wizard'),
    url(r'^(?P<app_name>[\w-]+)/(?P<model_name>[\w-]+)/$', 'reports_view', name='reports_view'),
    )
