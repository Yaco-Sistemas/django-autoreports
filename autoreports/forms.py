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

from django import forms

from django.utils.translation import ugettext_lazy as _

from autoreports.model_forms import ReportModelFormMetaclass
from autoreports.views import reports_view

from formadmin.forms import FormAdminDjango


class BaseReportForm(forms.ModelForm):

    __metaclass__ = ReportModelFormMetaclass


class ReportForm(BaseReportForm):

    use_initial = True

    def __init__(self, is_admin=False, use_subfix=True, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        if is_admin:
            self.__unicode__ = self.as_django_admin


class ReportDisplayForm(ReportForm, FormAdminDjango):

    def __init__(self, *args, **kwargs):
        super(ReportDisplayForm, self).__init__(*args, **kwargs)
        choices = [(field_name, unicode(field.label)) for field_name, field in self.fields.items()]
        self.fields = {}
        self.fields = {'__report_display_fields_choices': forms.MultipleChoiceField(
                                                            label=_('Report display fields'),
                                                            widget=forms.CheckboxSelectMultiple(),
                                                            choices=choices,
                                                            initial=dict(choices).keys(),
                                                            required=False)}


class ReportFilterForm(ReportForm, FormAdminDjango):

    def validate_unique(self):
        pass

    def is_valid(self):
        fields_required = []
        for key, field in self.fields.items():
            if field.required:
                fields_required.append(key)
                field.required = False
        valid = super(ReportFilterForm, self).is_valid()
        for field_required in fields_required:
            self.fields[field_required].required = True
        return valid

    def get_report(self, request, queryset, form_display, report, report_to, api=None):
        list_headers = []
        report_display_fields = form_display.cleaned_data.get('__report_display_fields_choices', [])
        choices_display_fields = dict(form_display.fields['__report_display_fields_choices'].choices)
        for key in report_display_fields:
            label = choices_display_fields[key]
            list_headers.append(unicode(label).encode('utf-8'))
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_display_fields,
                 list_headers=list_headers,
                 queryset=queryset,
                 report=report,
                 report_to=report_to,
                 api=api)
