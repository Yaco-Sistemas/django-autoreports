import collections

from copy import copy

from django import forms
from django.conf import settings
from django.contrib.admin.widgets import AdminSplitDateTime, AdminDateWidget
from django.db.models import ObjectDoesNotExist
from django.template.loader import render_to_string
from django.utils.translation import get_language
from django.utils.translation import ugettext as _

from autoreports.forms import BaseReportForm
from autoreports.model_forms import modelform_factory
from autoreports.utils import (get_fields_from_model, get_field_from_model,
                               parsed_field_name, transmeta_field_name, SEPARATED_FIELD)
from autoreports.wizards import ModelFieldForm, WizardField, WizardAdminField


class BaseReportField(object):

    def __init__(self, model, field, field_name=None, instance=None, treatment_transmeta=True, *args, **kwargs):
        super(BaseReportField, self).__init__(*args, **kwargs)
        self.model = model
        self.field = field
        self.field_name = field_name or self.field.name
        if treatment_transmeta:
            self._treatment_transmeta()
        self.field_name_parsed = self.field_name.replace(SEPARATED_FIELD, '__')
        self.instance = instance

    def get_verbose_name(self):
        return self.field.verbose_name

    def get_help_text(self):
        return self.field.help_text

    def get_filter_default(self):
        return 'icontains'

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact (case-sensitive)')),
                ('iexact', _('Exact (case-insensitive)')),
                ('contains', _('Contains (case-sensitive)')),
                ('icontains', _('Contains (case-insensitive)')),
                ('startswith', _('Starts with (case-sensitive)')),
                ('istartswith', _('Starts with (case-insensitive)')),
                ('endswith', _('Ends with (case-sensitive)')),
                ('iendswith', _('Ends with (case-insensitive)')),
                ('lt', _('Less than')),
                ('lte', _('Less than or equal')),
                ('gt', _('Greater than')),
                ('gte', _('Greater than or equal')),
                ('in', _('In (coma separated list)')),
                #('isnull', _('Is empty')),)
                )

    @classmethod
    def get_widgets_initial(self):
        return ('', '-----')

    @classmethod
    def get_widgets_available(self):
        return tuple()

    def _get_widget_from_opts(self, opts):
        return opts and opts.get('widget', None) or None

    def change_widget(self, field, opts=None):
        return field

    def change_value(self, value, key, request_get):
        return (value, request_get)

    def get_value(self, obj, field_name=None):
        field_name = field_name or self.field_name_parsed
        return getattr(obj, field_name)

    def get_label_to_opts(self, opts):
        autoreports_i18n = getattr(settings, 'AUTOREPORTS_I18N', False)
        if not autoreports_i18n:
            return opts.get('label', None)
        lang = get_language()
        return opts.get('label_%s' % lang, None)

    def get_help_text_to_opts(self, opts):
        autoreports_i18n = getattr(settings, 'AUTOREPORTS_I18N', False)
        if not autoreports_i18n:
            return opts.get('help_text', None)
        lang = get_language()
        return opts.get('help_text_%s' % lang, None)

    def get_basic_field_form(self, form, field_name):
        return form.base_fields[field_name]

    def get_field_form(self, opts=None, default=True,
                       fields_form_filter=None, fields_form_display=None):
        prefix, field_name = parsed_field_name(self.field_name)
        form = modelform_factory(self.model, form=BaseReportForm, fields=[field_name])
        field = self.get_basic_field_form(form, field_name)
        autoreports_initial = getattr(settings, 'AUTOREPORTS_INITIAL', True)
        autoreports_subfix = getattr(settings, 'AUTOREPORTS_SUBFIX', True)
        if not autoreports_initial:
            field.initial = None
        if opts:
            help_text = self.get_help_text_to_opts(opts)
            display = opts.get('display', None)
            filters = opts.get('filters', [])
            label = self.get_label_to_opts(opts)
            if label:
                field.label = label
            if help_text:
                field.help_text = help_text
            if display:
                fields_form_display[self.field_name] = copy(field)
            for fil in filters:
                field_copy = copy(field)
                field_name_subfix = "%s__%s" % (self.field_name_parsed, fil)
                if autoreports_subfix:
                    field_label = u"%s (%s)" % (field_copy.label, dict(self.get_filters())[fil])
                    field_copy.label = field_label
                fields_form_filter[field_name_subfix] = self.change_widget(field_copy, opts)
        else:
            if default:
                fil = self.get_filter_default()
                if fil is None:
                    return (fields_form_filter, fields_form_display)
                field_name_subfix = "%s__%s" % (self.field_name_parsed, fil)
                if autoreports_subfix:
                    field_label = u"%s (%s)" % (field.label, dict(self.get_filters())[fil])
                field.label = field_label
                fields_form_filter[field_name_subfix] = self.change_widget(field)
            else:
                fields_form_display[self.field_name] = field
        return (fields_form_filter, fields_form_display)

    def get_class_form(self, is_admin=True):
        if is_admin:
            return WizardAdminField
        return WizardField

    def get_form(self, is_admin=True):
        wizard_class = self.get_class_form(is_admin)
        return wizard_class(self,
                          instance=self.instance,
                          prefix=id(self))

    def render_model_field(self, form, model, is_admin=True):
        modelfieldform = ModelFieldForm(initial={'app_label': model._meta.app_label,
                                                 'module_name': model._meta.module_name,
                                                 'field_name': self.field_name},
                                        instance=self.instance,
                                        prefix=form.prefix)
        return unicode(modelfieldform)

    def extra_wizard_fields(self):
        return {}

    def render_wizard(self, is_admin=True):
        return unicode(self.get_form(is_admin))

    def render_admin(self, modelfieldform, wizard):
        return "<div class='adaptor'>%s %s <h2 class='removeAdaptor'>%s</h2></div>" % (modelfieldform,
                                                                                       wizard,
                                                                                       _("Remove"))

    def render(self, form, model, is_admin=True):
        modelfieldform = self.render_model_field(form, model)
        wizard = self.render_wizard(is_admin)
        if is_admin:
            return self.render_admin(modelfieldform, wizard)
        return "%s %s" % (modelfieldform, wizard)

    def render_instance(self, is_admin=True):
        wizard = self.get_form(is_admin)
        content_type = self.instance.content_type
        model, field = get_field_from_model(content_type.model_class(), self.field_name)
        return self.render(wizard,
                           model,
                           is_admin)

    def _treatment_transmeta(self):
        self.field_name = transmeta_field_name(self.field, self.field_name)


class TextFieldReportField(BaseReportField):

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(), ('textarea', _('Text Area')),)

    def get_filter_default(self):
        return 'icontains'

    def change_widget(self, field, opts=None):
        widget = self._get_widget_from_opts(opts)
        if widget == 'textarea':
            field.widget = forms.Textarea()
        else:
            field.widget = forms.TextInput()
        return field

    def extra_wizard_fields(self):
        prefix, field_name = parsed_field_name(self.field_name)
        prefix = SEPARATED_FIELD.join(prefix)
        fields = get_fields_from_model(self.model, adaptors=(TextFieldReportField,))
        current_field_name = self.field_name.split(SEPARATED_FIELD)[-1]
        choices = [(f['name'], f['verbose_name']) for f in fields[0] if f['name'] != current_field_name]
        if not choices:
            return {}
        initial = None
        if self.instance:
            field_options = self.instance.options.get(self.field_name, None)
            if field_options:
                initial = field_options.get('other_fields', None)
        return {'other_fields': forms.MultipleChoiceField(label=_('Other fields to filter'),
                                                    required=False,
                                                    choices=choices,
                                                    widget=forms.CheckboxSelectMultiple,
                                                    initial=initial,
                                                    help_text=_('Choose other fields, when you filter with this field, you will search in these also'))}

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact (case-sensitive)')),
                ('iexact', _('Exact (case-insensitive)')),
                ('contains', _('Contains (case-sensitive)')),
                ('icontains', _('Contains (case-insensitive)')),
                ('startswith', _('Starts with (case-sensitive)')),
                ('istartswith', _('Starts with (case-insensitive)')),
                ('endswith', _('Ends with (case-sensitive)')),
                ('iendswith', _('Ends with (case-insensitive)')),
                #('isnull', _('Is empty')),
                )


class ProviderSelectMultiple(object):

    def change_value_multiple(self, value, key, request_get):
        new_key = key.replace('__%s' % self.get_filter_default(), '__in')
        request_get.setlist(new_key, value)
        del request_get[key]

    def change_widget_multiple(self, field, choices):
        return forms.MultipleChoiceField(label=field.label,
                                          choices=choices,
                                          help_text=field.help_text,
                                          initial=(field.initial,))


class ChoicesFieldReportField(TextFieldReportField, ProviderSelectMultiple):

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(), ('selectmultiple', _('Select Multiple')),)

    def get_value(self, obj, field_name=None):
        field_name = field_name or self.field_name_parsed
        choice_display = getattr(obj, 'get_%s_display' % field_name, None)
        if choice_display and callable(choice_display):
            return choice_display()
        return super(ChoicesFieldReportField, self).get_value(obj, field_name)

    def get_filter_default(self):
        return 'exact'

    def change_value(self, value, key, request_get):
        if not value:
            del request_get[key]
        elif isinstance(value, list):
            self.change_value_multiple(value, key, request_get)
        return (value, request_get)

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty')),)
                )

    def extra_wizard_fields(self):
        return super(TextFieldReportField, self).extra_wizard_fields()

    def change_widget(self, field, opts=None):
        widget = self._get_widget_from_opts(opts)
        new_choices = [self.get_widgets_initial()] + field.widget.choices
        if widget == 'selectmultiple':
            field = self.change_widget_multiple(field, new_choices)
        field.widget.choices = new_choices
        return field


class NumberFieldReportField(BaseReportField):

    def get_filter_default(self):
        return 'exact'

    def change_value(self, value, key, request_get):
        if value.isnumeric():
            return (value, request_get)
        del request_get[key]
        return (value, request_get)

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact (case-sensitive)')),
                ('lt', _('Less than')),
                ('lte', _('Less than or equal')),
                ('gt', _('Greater than')),
                ('gte', _('Greater than or equal')),)


class AutoNumberFieldReportField(NumberFieldReportField):

    def get_basic_field_form(self, form, field_name):
        return forms.IntegerField(label=self.get_verbose_name())


class DateFieldReportField(BaseReportField):

    def get_filter_default(self):
        return 'exact'

    def change_widget(self, field, opts=None):
        field.widget = AdminDateWidget()
        return field

    def parser_date(self, value):
        try:
            return self.field.formfield().clean(value)
        except forms.ValidationError:
            return value

    def change_value(self, value, key, request_get):
        if not value:
            del request_get[key]
        return (self.parser_date(value), request_get)

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                ('lt', _('Less than')),
                ('lte', _('Less than or equal')),
                ('gt', _('Greater than')),
                ('gte', _('Greater than or equal')),
                #('isnull', _('Is empty')),
                )


class DateTimeFieldReportField(DateFieldReportField):

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(), ('date', _('Date')),)

    def change_widget(self, field, opts=None):
        field.widget = AdminSplitDateTime()
        return field

    def change_value(self, value, key, request_get):
        if key.endswith('_0'):
            key_1 = key.replace('_0', '_1')
            if not key_1 in request_get:
                return value
            key_without_prefix = key.replace('_0', '')
            if request_get[key] and request_get[key_1]:
                value = "%s %s" % (request_get[key],
                                    request_get[key_1])
                value = self.parser_date(value)
                request_get[key_without_prefix] = value
            initial_date = 'initial-%s' % key_without_prefix
            if request_get.get(initial_date, None):
                del request_get['initial-%s' % key_without_prefix]
            del request_get[key]
            del request_get[key_1]
        return (value, request_get)


class BooleanFieldReportField(BaseReportField):

    def change_widget(self, field, opts=None):
        choices = (('', '--------'),
                   ('0', _('No')),
                   ('1', _('Yes')),)

        field.widget = forms.Select(choices=choices)
        return field

    def change_value(self, value, key, request_get):
        if value == '0':
            return (False, request_get)
        elif value == '1':
            return (True, request_get)
        elif key in request_get:
            del request_get[key]
        return (value, request_get)

    def get_filter_default(self):
        return 'exact'

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty'))
                )


class RelatedReportField(BaseReportField):

    def _treatment_transmeta(self):
        pass

    def _post_preccessing_get_value(self, value):
        if isinstance(value, collections.Iterable):
            if len(value) == 0:
                return None
            elif len(value) == 1:
                return value[0]
        return value

    def get_filter_default(self):
        return 'exact'

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty')),
               )


class RelatedReverseField(RelatedReportField):

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(), ('selectmultiple', _('Select Multiple')),)

    def get_basic_field_form(self, form, field_name):
        return forms.ModelMultipleChoiceField(label=self.get_verbose_name(),
                                        queryset=self.field.model.objects.all())

    def get_value(self, obj, field_name=None):
        field_name = self.field.get_accessor_name()
        return self._post_preccessing_get_value(getattr(obj, field_name).all())

    def get_verbose_name(self):
        return self.field.field.verbose_name

    def get_help_text(self):
        return self.field.field.help_text


class RelatedDirectField(RelatedReportField):
    pass


class ForeingKeyReportField(RelatedDirectField):

    def change_value(self, value, key, request_get):
        if not value:
            del request_get[key]
        return (value, request_get)

    def get_value(self, obj, field_name=None):
        try:
            return super(ForeingKeyReportField, self).get_value(obj, field_name)
        except ObjectDoesNotExist:
            return None  # Intigrity Error


class M2MReportField(RelatedDirectField):

    def get_value(self, obj, field_name=None):
        return self._post_preccessing_get_value(
                    super(RelatedDirectField, self).get_value(obj, field_name).all())


class FuncField(BaseReportField):

    from autoreports.utils import add_domain
    middleware_value = {'get_absolute_url': add_domain}

    def get_basic_field_form(self, form, field_name):
        class FakeFuncFieldForm(object):

            def __init__(self, label, help_text):
                self.label = label
                self.help_text = help_text

        return FakeFuncFieldForm(label=self.get_verbose_name(),
                                        help_text=self.get_help_text())

    def get_verbose_name(self):
        label = getattr(self.field, 'label', '')
        if label:
            return label
        prefix, field_name = parsed_field_name(self.field_name)
        return field_name

    def get_help_text(self):
        return getattr(self.field, 'short_description', '')

    def get_value(self, obj, field_name=None):
        func_args = self.field.im_func.func_code.co_argcount
        if func_args == 1:
            value = super(FuncField, self).get_value(obj, field_name)()
        elif func_args == 2:
            value = self.field(obj)
        else:
            value = 'error'
        if field_name in self.middleware_value:
            value = self.middleware_value[field_name](value)
        return value

    def _treatment_transmeta(self):
        pass

    def get_filter_default(self):
        return None

    @classmethod
    def get_filters(self):
        return tuple()

    def render_admin(self, modelfieldform, wizard):
        try:
            from inspect import getsource
            from pygments import highlight
            from pygments.lexers import PythonLexer
            from pygments.formatters import HtmlFormatter
            code = getsource(self.field)
            code = highlight(code, PythonLexer(), HtmlFormatter(cssclass="syntax hiddenElement"))
        except TypeError:
            code = ""
        adaptor_help = render_to_string("autoreports/fields/func_field_wizard.html", {'code': code})
        return "<div class='adaptor'>%s %s %s<h2 class='removeAdaptor'>%s</h2></div>" % (modelfieldform,
                                                                                         adaptor_help,
                                                                                         wizard,
                                                                                         _("Remove"))


class PropertyField(FuncField):

    def get_value(self, obj, field_name=None):
        return super(FuncField, self).get_value(obj, field_name)


class GenericFKField(PropertyField):
    pass
