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

from django import template
from django.conf import settings
from django.conf.urls.defaults import patterns, url
from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.templatetags.admin_list import result_headers
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.functional import update_wrapper

from autoreports.api import ReportApi
from autoreports.main import AutoReportChangeList
from autoreports.models import Report
from autoreports.utils import get_fields_from_model, get_adaptors_from_report
from autoreports.views import reports_view, set_filters_search_fields
from autoreports.wizards import ReportNameAdminForm, ReportNameForm, ModelFieldForm, WizardField


class ReportAdmin(ReportApi):

    is_admin = True

    def get_urls(self):

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
                url(r'^report/wizard/(?P<report_id>\d+)/$',
                      wrap(self.report_edit_wizard),
                      name='%s_%s_report_edit_wizard' % info),
                url(r'^report/advance/$',
                      wrap(self.report_advance),
                      name='%s_%s_report_advance' % info),
                url(r'^report/quick/$',
                      wrap(self.report_quick),
                      name='%s_%s_report_quick' % info),
                url(r'^report/(?P<report_id>\d+)/$',
                      wrap(self.report_view),
                      name='%s_%s_report_view' % info),
                url(r'^report/(?P<report_id>\d+)/delete/$',
                      self.delete_report,
                      name='%s_%s_delete_report' % info),
        ) + urlpatterns
        return urlpatterns

    def _get_change_list(self, request, model, cl_options, report):
        list_display = cl_options.get('list_display', self.list_display)
        if 'action_checkbox' in list_display:
            list_display = list_display[1:]
        list_display_links = cl_options.get('list_display_links', self.list_display_links)
        list_filter = cl_options.get('list_filter', tuple())
        date_hierarchy = cl_options.get('date_hierarchy', self.date_hierarchy)
        search_fields = cl_options.get('search_fields', tuple())
        list_select_related = cl_options.get('list_select_related', self.list_select_related)
        list_per_page = cl_options.get('list_per_page', self.list_per_page)
        list_editable = cl_options.get('list_editable', getattr(self, 'list_editable', None))
        prefix_url = cl_options.get('prefix_url', '../../')
        model_admin = self
        if model != self.model:
            model_admin = admin.site._registry[model]
        try:
            cl = AutoReportChangeList(request, model, prefix_url, report, list_display, list_display_links, list_filter,
                date_hierarchy, search_fields, list_select_related, list_per_page, list_editable, model_admin)
            cl.formset = None
            return cl
        except TypeError:
            return AutoReportChangeList(request, model, prefix_url, report, list_display, list_display_links, list_filter,
                date_hierarchy, search_fields, list_select_related, list_per_page, model_admin)

    def _get_extra_context_fake_change_list(self, model, request, extra_context=None, cl_options=None, report=None):
        extra_context = extra_context or {}
        opts = model._meta
        app_label = opts.app_label
        cl_options = cl_options or {}
        cl = self._get_change_list(request, model, cl_options, report)
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
        return context

    def report_list(self, request, extra_context=None):
        "The 'change list' admin view for this model."
        cl_options = {}
        cl_options['list_display'] = ('name', )
        cl_options['list_display_links'] = tuple()
        cl_options['list_filter'] = tuple()
        cl_options['date_hierarchy'] = None
        cl_options['search_fields'] = tuple()
        cl_options['list_select_related'] = False
        cl_options['list_per_page'] = 100
        cl_options['prefix_url'] = 'wizard/'
        model = Report
        context = self._get_extra_context_fake_change_list(model, request, extra_context, cl_options)
        opts = model._meta
        app_label = opts.app_label
        content_type = ContentType.objects.get_for_model(self.model)
        cl = context['cl']
        cl.query_set = cl.query_set.filter(content_type=content_type)
        cl.result_list = cl.query_set._clone()
        context['cl'] = cl
        return render_to_response(getattr(self, 'change_report_list_template', None) or [
            'autoreports/admin/%s/%s/report_list.html' % (app_label, opts.object_name.lower()),
            'autoreports/admin/%s/report_list.html' % app_label,
            'autoreports/admin/report_list.html',
        ], context, context_instance=template.RequestContext(request))

    def report_wizard(self, request,
                            template_name='autoreports/admin/autoreports_wizard.html',
                            extra_context=None,
                            model=Report,
                            form_top_class=ReportNameAdminForm,
                            content_type=None):
        return self.report_api_wizard(request,
                                      template_name=template_name,
                                      extra_context=extra_context,
                                      model=model,
                                      form_top_class=form_top_class,
                                      content_type=content_type)

    def report_edit_wizard(self, request, report_id,
                          template_name='autoreports/admin/autoreports_wizard.html',
                          extra_context=None,
                          model=Report,
                          form_top_class=ReportNameAdminForm,
                          content_type=None):
        report = model.objects.get(pk=report_id)
        return self.report_api_wizard(request,
                                      report=report,
                                      template_name=template_name,
                                      extra_context=extra_context,
                                      model=model,
                                      form_top_class=form_top_class,
                                      content_type=content_type)

    def report_api_wizard(self, request,
                          report=None,
                          template_name='autoreports/admin/autoreports_wizard.html',
                          extra_context=None,
                          model=Report,
                          form_top_class=ReportNameForm,
                          model_to_export=None,
                          content_type=None):
        model_to_export = model_to_export or self.model
        content_type = content_type or ContentType.objects.get_for_model(model_to_export)
        data = None
        adaptors = []
        form_top_initial = {}
        if request.method == 'POST':
            data = request.POST
        elif report:
            adaptors = get_adaptors_from_report(report)
            form_top_initial['prefixes'] = ", ".join([unicode(adaptor.get_form().prefix) for adaptor in adaptors])
        form_top = form_top_class(instance=report, data=data, initial=form_top_initial)
        options = {}
        if form_top.is_valid():
            for prefix in form_top.cleaned_data.get('prefixes', []):
                model_field_form = ModelFieldForm(data=data,
                                                  prefix=prefix)
                if model_field_form.is_valid():
                    field_name = model_field_form.cleaned_data.get('field_name')
                    adaptor = model_field_form.get_adaptor()
                    wizardfield = WizardField(data=data,
                                              autoreport_field=adaptor,
                                              prefix=prefix)
                    if wizardfield.is_valid():
                        options[field_name] = wizardfield.cleaned_data
            name = form_top.cleaned_data.get('name', None) or 'report of %s' % unicode(model_to_export._meta.verbose_name)
            report_created = self._create_report(model, content_type, name, options, form_top.instance)
            redirect = report_created.get_redirect_wizard(report)
            return HttpResponseRedirect(redirect)
        fields, funcs = get_fields_from_model(content_type.model_class())
        context = {'add': report is None,
                   'report': report,
                   'opts': self.opts,
                   'fields': fields,
                   'funcs': funcs,
                   'ADMIN_MEDIA_PREFIX': settings.ADMIN_MEDIA_PREFIX,
                   'template_base': "admin/base_site.html",
                   'form_top': form_top,
                   'module_name': content_type.model,
                   'app_label': content_type.app_label,
                   'adaptors': adaptors,
                  }
        extra_context = extra_context or {}
        context.update(extra_context)
        return render_to_response(template_name,
                                  context,
                                  context_instance=RequestContext(request))

    def _create_report(self, model, content_type, name, options, report=None):
        report.content_type = content_type
        report.name = name
        report.options = options
        report.save()
        return report

    def report_view(self, request, report_id, queryset=None, template_name='autoreports/admin/autoreports_form.html', extra_context=None):
        report = Report.objects.get(pk=report_id)
        return self.report_advance(request, report=report, queryset=queryset, template_name=template_name, extra_context=extra_context)

    def report_advance(self, request, report=None, queryset=None, template_name='autoreports/admin/autoreports_form.html', extra_context=None):
        context = {'opts': self.opts,
                   'template_base': "admin/change_list.html",
                    }
        extra_context = extra_context or {}
        context = self._get_extra_context_fake_change_list(self.model, request, context, report=report)
        cl = context.get('cl', None)
        context['_adavanced_filters'] = cl and cl._adavanced_filters or None
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
                if not header.get('url', None) and not getattr(self.model, fields[i - j], None):
                    del fields[i - j]
                    j = j + 1
        except IncorrectLookupParameters:
            pass

        return reports_view(request, self.model._meta.app_label, self.model._meta.module_name,
                            fields=fields, list_headers=None, ordering=ordering, filters=filters,
                            model_admin=self, queryset=queryset,
                            report_to='csv')

    def delete_report(self, request, report_id):
        report = get_object_or_404(Report, id=report_id)
        report.delete()
        info = self.model._meta.app_label, self.model._meta.module_name
        return HttpResponseRedirect('/admin/%s/%s/' % info)
