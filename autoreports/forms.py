from django import forms

from django.template.loader import render_to_string

from django.utils.datastructures import SortedDict
from django.utils.translation import get_language
from django.utils.translation import ugettext_lazy as _

from autoreports.models import ReportModelFormMetaclass, modelform_factory
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

    def __init__(self, fields, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        model = self._meta.model
        translatable_fields = self.get_translatable_fields(model)
        translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]

        fields_lang = ['%s_%s' %(field, get_language()) for field in fields]
        fields_real = SortedDict({})
        self.callables_choices = []
        for field in fields:
            field_real = self.simply_field(model, field, field, fields_real, translatable_fields_lang)
            if not field_real:
                self.related_field(field, field, model, fields_real)
        self.fields_real = fields_real

    def get_field(self, field, fields, model):
        if field in fields:
            return fields[field]
        form = modelform_factory(model=model, form=BaseReportForm)()
        return form.base_fields.get(field, None)

    def set_field(self, field_name, field, fields_real):
        print '%s %s' %(field_name, field)
        choices = getattr(field, 'choices', None)
        if choices and isinstance(choices, list):
            field.choices = [('', '---------'), ] + choices
        queryset = getattr(field, 'queryset', None)
        if queryset:
            field.queryset = queryset.filter(pk__lte=5)
        fields_real[field_name] = field

    def simply_field(self, model, field_name, field, fields_real, translatable_fields_lang):
        field_real = None
        if field in self.fields: # fields normales
            field_real = self.get_field(field, self.fields, model)
            if getattr(model, field, None): # m2m or fk
                self.set_field('%s__id__in' % field_name, field_real, fields_real)
            else:
                self.set_field('%s__icontains' % field_name, field_real, fields_real)
        else:
            field_trans = '%s_%s' % (field, get_language())
            field_name_trans = '%s_%s' % (field, get_language())
            if field_trans in translatable_fields_lang: # transmeta fields
                field_real = self.get_field(field_trans, self.fields, model)
                self.set_field('%s__icontains' % field_name_trans, field_real, fields_real)
        return field_real

    def related_field(self, field_name, field, model, fields_real):
        field_split = field.split('__')
        field = '__'.join(field_split[1:])
        if callable(getattr(model, field, None)) or callable(getattr(model, '__%s' % field, None)):
            field_callable = getattr(model, field, None) or getattr(model, '__%s' % field, None)
            self.callables_choices.append((field_name, unicode(getattr(field_callable, 'short_description', field_name))))
            return
        relation = getattr(model, field_split[0])
        relation_field = getattr(relation, 'field', None)
        if relation_field:
            model_next = relation_field.formfield().queryset.model
            if '__' in field:
                self.related_field(field_name, field, model_next, fields_real)
                return

            translatable_fields = self.get_translatable_fields(model_next)
            translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]
            field_real = self.simply_field(model_next, field_name, field, fields_real, translatable_fields)

            if not field_real:
                if field: # reverse relation
                    m2mrelated = getattr(model_next, field, None)
                    if m2mrelated and getattr(m2mrelated, 'related', None) and getattr(m2mrelated.related, 'model', None):
                        model_queryset = m2mrelated.related.model
                        f = forms.ModelChoiceField(queryset=model_queryset.objects.all())
                        f.label = model_queryset._meta.verbose_name
                        self.set_field('%s__id__in' % field_name, f, fields_real)
                else:
                    self.set_field('%s__id__in' % field_name, relation.field.formfield(), fields_real)

    def get_translatable_fields(self, cls):
        classes = cls._meta.get_parent_list()
        classes.add(cls)
        translatable_fields = []
        [translatable_fields.extend(cl._meta.translatable_fields) for cl in classes if getattr(cl._meta, 'translatable_fields', None)]
        return translatable_fields


class ReportDisplayForm(ReportForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportDisplayForm, self).__init__(fields, *args, **kwargs)
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

    def get_report(self, request, queryset, report_display_fields):
        report_filter_fields = [field.replace('__icontains', '').replace('__iexact', '').replace('__id__in', '')
                        for field in report_display_fields]
        list_headers = [unicode(field.label).encode('utf-8') for key, field in self.fields.items() if key in report_display_fields]
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_filter_fields,
                 list_headers=list_headers,
                 queryset=queryset)
