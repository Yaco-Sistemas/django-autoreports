from django import forms
from django.forms.models import modelform_factory
from django.template.loader import render_to_string

from django.utils.translation import get_language

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


class ReportForm(object):

    def __init__(self, fields, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        translatable_fields = self.get_translatable_fields(self._meta.model)
        translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]
        fields_lang = ['%s_%s' %(field, get_language()) for field in fields]
        fields_real = {}
        for field in fields:
            field_real = self.simply_field(field, fields_real, translatable_fields_lang)
            if not field_real:
                self.related_field(field, field, self._meta.model, fields_real)
        self.fields_real = fields_real

    def get_field(self, field, fields, model):
        if field in fields:
            return fields[field]
        form = modelform_factory(model)()
        return form.base_fields.get(field, None)

    def set_field(self, field_name, field, fields_real):
        if field:
            fields_real[field_name] = field

    def simply_field(self, field, fields_real, translatable_fields_lang):
        field_real = None
        model = self._meta.model
        if field in self.fields: # fields normales
            field_real = self.get_field(field, self.fields, model)
            if getattr(model, field, None): # m2m
                self.set_field('%s__id__in' % field, field_real, fields_real)
            else:
                self.set_field('%s__icontains' % field, field_real, fields_real)
        else:
            field_trans = '%s_%s' %(field, get_language())
            if field_trans in translatable_fields_lang: # transmeta fields
                field_real = self.get_field(field_trans, self.fields, model)
                self.set_field('%s__icontains' % field_trans, field_real, fields_real)
        return field_real

    def related_field(self, field_name, field, model, fields_real):
        field_split = field.split('__')
        relation = getattr(model, field_split[0])
        field = '__'.join(field_split[1:])
        relation_field = getattr(relation, 'field', None)
        if relation_field:
            model_next = relation_field.formfield().queryset.model
            if '__' in field:
                self.related_field(field_name, field, model_next, fields_real)
                return
            form = modelform_factory(model_next)
            if not field:
                self.set_field('%s__id__in' % field_name, relation.field.formfield(), fields_real)
            else:
                self.set_field('%s__icontains' % field_name, form.base_fields[field], fields_real)

    def get_translatable_fields(self, cls):
        classes = cls._meta.get_parent_list()
        classes.add(cls)
        translatable_fields = []
        [translatable_fields.extend(cl._meta.translatable_fields) for cl in classes if getattr(cl._meta, 'translatable_fields', None)]
        return translatable_fields


class ReportDisplayForm(ReportForm, forms.ModelForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportDisplayForm, self).__init__(fields, *args, **kwargs)
        choices = [(field_name, unicode(field.label)) for field_name, field in self.fields_real.items()]
        callables_choices = self.get_callables_choices(fields)
        choices.extend(callables_choices)
        self.fields = {'__report_display_fields_choices': forms.MultipleChoiceField(
                                                    widget=forms.CheckboxSelectMultiple(),
                                                    choices=choices,
                                                    initial=dict(choices).keys()),
                      }

    def get_callables_choices(self, fields):
        model = self._meta.model
        callables_choices = []
        for field_name in fields:
            field = getattr(model, field_name, None)
            if field and callable(field):
                callables_choices.append((field_name, unicode(getattr(field, 'short_description', field_name))))
        return callables_choices


class ReportFilterForm(ReportForm, forms.ModelForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportFilterForm, self).__init__(fields, *args, **kwargs)
        self.fields = self.fields_real

    def get_report(self, request, queryset, report_display_fields):
        report_filter_fields = [field.replace('__icontains', '').replace('__iexact', '').replace('__id__in', '')
                            for field in report_display_fields]
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_filter_fields,
                 queryset=queryset)
