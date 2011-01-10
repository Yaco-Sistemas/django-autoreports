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

from django.contrib.admin.widgets import AdminSplitDateTime, AdminDateWidget
from django.template.loader import render_to_string

from django.utils import simplejson
from django.utils.datastructures import SortedDict
from django.utils.translation import get_language
from django.utils.translation import ugettext_lazy as _

from autoreports.models import ReportModelFormMetaclass, modelform_factory, Report
from autoreports.utils import CHOICES_ALL, change_widget
from autoreports.views import reports_view


class FormAdminDjango(object):
    """
    Abstract class implemented to provide form django admin like
    Usage::

       class FooForm(forms.Form, FormAdminDjango):
          ...
    """

    def as_django_admin(self):
        return render_to_string('autoreports/form_admin_django.html', {'form': self, })


class BaseReportForm(forms.ModelForm):

    __metaclass__ = ReportModelFormMetaclass


class ReportForm(BaseReportForm):

    use_initial = True

    def __init__(self, fields, is_admin=False, report=None, use_subfix=True, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        model = self._meta.model
        self.is_admin = is_admin
        self.report = report
        if report and getattr(report, 'advanced_options', None):
            self.advanced_options = simplejson.loads(report.advanced_options)
        else:
            self.advanced_options = {}
        self.use_subfix = use_subfix
        fields_real = self.get_real_fields(model, fields)
        self.fields_real = fields_real

    def get_real_fields(self, model, fields):
        translatable_fields = self.get_translatable_fields(model)
        translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]
        fields_lang = ['%s_%s' %(field, get_language()) for field in fields]
        fields_real = SortedDict({})
        self.callables_choices = []
        for field in fields:
            field_real = self.get_real_field(model, field, fields_real, translatable_fields_lang)
        return fields_real

    def get_real_field(self, model, field, fields_real=None, translatable_fields_lang=None):
        if fields_real is None:
            fields_real = SortedDict({})
        translatable_fields_lang = translatable_fields_lang or []
        field_real = self.get_real_model_field(model, field, field, fields_real, translatable_fields_lang)
        if not field_real:
            if not self._is_callable(model, field, field):
                field_real = self.get_real_related_field(field, field, model, fields_real)
        return field_real

    def get_real_model_field(self, model, field_name, field, fields_real, translatable_fields_lang):
        field_real = None
        fields = modelform_factory(model, form=self.__class__).base_fields

        field, suffix = self._remove_suffix(field)
        if field in fields: # fields normales
            field_real = self._get_field(field, fields, model)
            if getattr(model, field, None): # m2m or fk
                return self._set_field(field_name, '__id__in', field_real, fields_real)
            else:
                if isinstance(field_real, forms.DateField) or isinstance(field_real, forms.DateTimeField):
                    if not self.report:
                        label = field_real.label
                        field_real.label = u"%s >=" % label
                    if isinstance(field_real, forms.DateTimeField):
                        field_real_split = forms.SplitDateTimeField()
                        fields = field_real_split.fields
                        field_real_split.__dict__ = field_real.__dict__
                        field_real_split.fields = fields
                        field_real = field_real_split
                        field_real.widget = AdminSplitDateTime()
                    else:
                        field_real.widget = AdminDateWidget()
                    field_real.show_hidden_initial = False
                    return self._set_field(field_name, '__gte', field_real, fields_real)
                    if not self.report:
                        from copy import deepcopy
                        field_real = deepcopy(field_real)
                        field_real.label = u"%s <=" % label
                        return self._set_field(field_name, '__lte', field_real, fields_real)
                elif isinstance(field_real, forms.BooleanField) or isinstance(field_real, forms.BooleanField):
                    field_real.widget = forms.RadioSelect(choices=((1, _('Yes')),
                                                                   (0, _('No')),
                                                        ))
                    return self._set_field(field_name, '', field_real, fields_real)
                elif isinstance(field_real, forms.IntegerField) or isinstance(field_real, forms.FloatField):
                    return self._set_field(field_name, '', field_real, fields_real)
                else:
                    return self._set_field(field_name, '__icontains', field_real, fields_real)
        else:
            field_trans = '%s_%s' % (field, get_language())
            field_name_trans = '%s_%s' % (field, get_language())
            if field_trans in translatable_fields_lang: # transmeta fields
                field_real = self._get_field(field_trans, self.fields, model)
                return self._set_field(field_name_trans, '__icontains', field_real, fields_real)
        return field_real

    def get_real_related_field(self, field_name, field, model, fields_real):
        field_split = field.split('__')
        field = '__'.join(field_split[1:])
        if self._is_callable(model, field, field_name):
            return
        relation = getattr(model, field_split[0], None)
        relation_field = relation and getattr(relation, 'field', None)
        if relation_field:
            model_next = relation_field.formfield().queryset.model
            if '__' in self._remove_suffix(field)[0]:
                self.get_real_related_field(field_name, field, model_next, fields_real)
                return

            translatable_fields = self.get_translatable_fields(model_next)
            translatable_fields_lang = ['%s_%s' %(translatable_field, get_language()) for translatable_field in translatable_fields]
            return self.get_real_model_field(model_next, field_name, field, fields_real, translatable_fields)
        else:
            model_next = model
            field_real = None
            field = field_split[0]
            last_relation = False

        if not field_real:
            if field: # reverse relation
                m2mrelated = getattr(model_next, field, None) or getattr(model_next, '%s_set' % field, None)
                if m2mrelated and getattr(m2mrelated, 'related', None) and getattr(m2mrelated.related, 'model', None):
                    model_queryset = m2mrelated.related.model
                    field = '__'.join(field_split[1:])
                    if last_relation or not field:
                        f = forms.ModelChoiceField(queryset=model_queryset.objects.all())
                        f.label = model_queryset._meta.verbose_name
                        return self._set_field(field_name, '__id__in', f, fields_real)
                    else:
                        if '__' in self._remove_suffix(field)[0]:
                            return self.get_real_related_field(field_name, '__'.join(field_split[1:]), model_queryset, fields_real)
                        translatable_fields = self.get_translatable_fields(model_queryset)
                        translatable_fields_lang = ['%s_%s' %(translatable_field, get_language()) for translatable_field in translatable_fields]
                        return self.get_real_model_field(model_queryset, field_name, field, fields_real, translatable_fields)

            else:
                return self._set_field(field_name, '__id__in', relation.field.formfield(), fields_real)

    def get_translatable_fields(self, cls):
        classes = cls._meta.get_parent_list()
        classes.add(cls)
        translatable_fields = []
        [translatable_fields.extend(cl._meta.translatable_fields) for cl in classes if getattr(cl._meta, 'translatable_fields', None)]
        return translatable_fields

    def _get_field(self, field, fields, model):
        if field in fields:
            return fields[field]
        form = modelform_factory(model=model, form=BaseReportForm)()
        return form.base_fields.get(field, None)

    def _set_field(self, field_name, subfix, field, fields_real):
        choices = getattr(field, 'choices', None)
        if choices and isinstance(choices, list):
            field.choices = [('', '---------'), ] + choices
        if not self.use_initial:
            field.initial = None
        if not self.report and self.use_subfix and subfix:
            field_name = '%s%s' %(field_name, subfix)
        field.help_text = field_name
        from copy import deepcopy
        field_copy = deepcopy(field)
        advanced_options_field = self.advanced_options.get(field_name, None)
        if self.advanced_options and advanced_options_field:
            widget = advanced_options_field.get('widget', None)
            if widget:
                change_widget(widget, field_copy)
            default_val = advanced_options_field.get('default', None)
            field_copy.initial = default_val
        fields_real[field_name] = field_copy
        return field

    def _remove_suffix(self, field):
        suffix = ''
        field_withput_suffix = field
        for choice, choice_name in CHOICES_ALL:
            if field.endswith('__%s' % choice):
                suffix = choice
                field_withput_suffix = field.replace('__%s' % choice, '')
        return (field_withput_suffix, suffix)

    def _is_callable(self, model, field, field_name):
        if callable(getattr(model, field, None)) or callable(getattr(model, '__%s' % field, None)):
            field_callable = getattr(model, field, None) or getattr(model, '__%s' % field, None)
            self.callables_choices.append((field_name, unicode(getattr(field_callable, 'short_description', field_name))))
            return True
        return False


class ReportDisplayForm(ReportForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportDisplayForm, self).__init__(fields, *args, **kwargs)
        if self.is_admin:
            self.__unicode__ = self.as_django_admin
        self.fields = {}
        if self.fields_real:
            choices = [(field_name, unicode(field.label)) for field_name, field in self.fields_real.items()]
            choices.extend(self.callables_choices)
            self.fields = {'__report_display_fields_choices': forms.MultipleChoiceField(
                                                        label=_('Report display fields'),
                                                        widget=forms.CheckboxSelectMultiple(),
                                                        choices=choices,
                                                        initial=dict(choices).keys()),
                        }


class ReportFilterForm(ReportForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportFilterForm, self).__init__(fields, *args, **kwargs)
        self.fields = self.fields_real
        if self.is_admin:
            self.__unicode__ = self.as_django_admin

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

    def get_report(self, request, queryset, report_display_fields, report_to):
        list_headers = []
        for key in report_display_fields:
            if not key in self.fields.keys():
                field = self.get_real_field(self._meta.model, key)
                label = field and field.label or key
            else:
                label = self.fields[key].label
            list_headers.append(unicode(label).encode('utf-8'))
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_display_fields,
                 list_headers=list_headers,
                 queryset=queryset,
                 report_to=report_to)


class ReportNameForm(BaseReportForm):

    def __init__(self, *args, **kwargs):
        super(ReportNameForm, self).__init__(*args, **kwargs)
        self.fields['name'].required = False

    class Meta:
        model = Report
        fields = ('name', )


class ReportNameAdminForm(ReportNameForm, FormAdminDjango):

    def __unicode__(self):
        return self.as_django_admin()
