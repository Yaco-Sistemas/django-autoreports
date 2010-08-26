from django import forms

from django.contrib.admin.widgets import AdminSplitDateTime, AdminDateWidget
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

    use_initial = True

    def __init__(self, fields, is_admin=False, *args, **kwargs):
        super(ReportForm, self).__init__(*args, **kwargs)
        model = self._meta.model
        self.is_admin = is_admin
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
        choices = getattr(field, 'choices', None)
        if choices and isinstance(choices, list):
            field.choices = [('', '---------'), ] + choices
        if not self.use_initial:
            field.initial = None
        fields_real[field_name] = field

    def simply_field(self, model, field_name, field, fields_real, translatable_fields_lang):
        field_real = None
        if model == self._meta.model:
            fields = self.fields
        else:
            fields = modelform_factory(model).base_fields
        if field in fields: # fields normales
            field_real = self.get_field(field, self.fields, model)
            if getattr(model, field, None): # m2m or fk
                self.set_field('%s__id__in' % field_name, field_real, fields_real)
            else:
                if isinstance(field_real, forms.DateField) or isinstance(field_real, forms.DateTimeField):
                    label = field_real.label
                    field_real.label = u"%s >=" % label
                    if self.is_admin:
                        if isinstance(field_real, forms.DateTimeField):
                            field_real.widget = AdminSplitDateTime()
                        else:
                            field_real.widget = AdminDateWidget()
                        field_real.show_hidden_initial = False
                    self.set_field('%s__gte' % field_name, field_real, fields_real)
                    from copy import deepcopy
                    field_real = deepcopy(field_real)
                    field_real.label = u"%s <=" % label
                    self.set_field('%s__lte' % field_name, field_real, fields_real)
                elif isinstance(field_real, forms.BooleanField) or isinstance(field_real, forms.BooleanField):
                    field_real.widget = forms.RadioSelect(choices=((1, _('Yes')),
                                                                   (0, _('No')),
                                                        ))
                    self.set_field(field_name, field_real, fields_real)
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
            last_relation = True
        else:
            model_next = model
            field_real = None
            field = field_split[0]
            last_relation = False

        if not field_real:
            if field: # reverse relation
                m2mrelated = getattr(model_next, field, None)
                if m2mrelated and getattr(m2mrelated, 'related', None) and getattr(m2mrelated.related, 'model', None):
                    model_queryset = m2mrelated.related.model
                    field = '__'.join(field_split[1:])
                    if last_relation or not field:
                        f = forms.ModelChoiceField(queryset=model_queryset.objects.all())
                        f.label = model_queryset._meta.verbose_name
                        self.set_field('%s__id__in' % field_name, f, fields_real)
                    else:
                        if '__' in field:
                            self.related_field(field_name, '__'.join(field_split[1:]), model_queryset, fields_real)
                            return
                        translatable_fields = self.get_translatable_fields(model_queryset)
                        translatable_fields_lang = ['%s_%s' %(field, get_language()) for field in translatable_fields]
                        field_real = self.simply_field(model_queryset, field_name, field, fields_real, translatable_fields)

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

    def get_report(self, request, queryset, report_display_fields, report_to):
        report_filter_fields = []
        for field in report_display_fields:
            if field.endswith('__lte') or field.endswith('__lte_0') or field.endswith('__lte_1'):
                continue
            else:
                field = field.replace('__icontains', '').replace('__iexact', '').replace('__id__in', '').replace('__gte', '').replace('__gte_0', '').replace('__gte_1', '')
            report_filter_fields.append(field)

        list_headers = []
        for key, field in self.fields.items():
            if not key in report_display_fields:
                continue
            if key.endswith('__lte') or key.endswith('__lte_0') or key.endswith('__lte_1'):
                continue
            elif key.endswith('__gte') or key.endswith('__gte_0') or key.endswith('__gte_1'):
                field.label = field.label[:-3]
            list_headers.append(unicode(field.label).encode('utf-8'))
        return reports_view(request,
                 self._meta.model._meta.app_label,
                 self._meta.model._meta.module_name,
                 fields=report_filter_fields,
                 list_headers=list_headers,
                 queryset=queryset,
                 report_to=report_to)
