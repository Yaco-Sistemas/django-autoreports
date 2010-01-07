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


class ReportForm(forms.ModelForm, FormAdminDjango):

    def __init__(self, fields, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        translatable_fields = self.get_translatable_fields(self._meta.model)
        translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]
        fields_lang = ['%s_%s' %(field, get_language()) for field in fields]
        fields_real = {}
        for field in fields:
            field_real = self.simply_field(field, fields_real, translatable_fields_lang)
            if not field_real:
                self.advanced_field(field, field, self._meta.model, fields_real)
        self.fields = fields_real

    def get_report(self, request, queryset):
        report_fields = [field.replace('__icontains', '').replace('__iexact', '').replace('__id__in', '')
                            for field in self.fields.keys()]
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_fields,
                 queryset=queryset)

    def simply_field(self, field, fields_real, translatable_fields_lang):
        field_real = None
        if field in self.fields: # fields normales
            field_real = self.fields[field]
            if getattr(self._meta.model, field, None): # m2m
                fields_real['%s__id__in' % field] = field_real
            else:
                fields_real['%s__icontains' % field] = field_real
        else:
            field_trans = '%s_%s' %(field, get_language())
            if field_trans in translatable_fields_lang: # transmeta fields
                field_real = self.fields[field_trans]
                fields_real['%s__icontains' % field_trans] = field_real
        return field_real

    def advanced_field(self, field_name, field, model, fields_real):
        field_split = field.split('__')
        relation = getattr(model, field_split[0])
        field = '__'.join(field_split[1:])
        model_next = relation.field.formfield().queryset.model
        if '__' in field:
            self.advanced_field(field_name, field, model_next, fields_real)
            return
        form = modelform_factory(model_next)
        if not field:
            fields_real['%s__id__in' % field_name] = relation.field.formfield()
        else:
            fields_real['%s__icontains' % field_name] = form.base_fields[field]

    def get_translatable_fields(self, cls):
        classes = cls._meta.get_parent_list()
        classes.add(cls)
        translatable_fields = []
        [translatable_fields.extend(cl._meta.translatable_fields) for cl in classes if getattr(cl._meta, 'translatable_fields', None)]
        return translatable_fields
