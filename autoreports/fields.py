import itertools

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
from autoreports.utils import (is_iterable, get_fields_from_model, get_field_from_model,
                               parsed_field_name, transmeta_field_name, SEPARATED_FIELD,
                               get_class_from_path)
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
        return ('', '---------')

    @classmethod
    def get_widgets_available(self):
        return tuple()

    def get_change_filter(self, fil, opts):
        return (fil, dict(self.get_filters())[fil])

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
                fil, verbose_fil = self.get_change_filter(fil, opts)
                field_name_subfix = "%s__%s" % (self.field_name_parsed, fil)
                if autoreports_subfix:
                    field_label = u"%s (%s)" % (field_copy.label, verbose_fil)
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
            wizard_admin_path = getattr(settings, 'AUTOREPORTS_WIZARDADMINFIELD', None)
            if not wizard_admin_path:
                return WizardAdminField
            else:
                return get_class_from_path(wizard_admin_path)
        wizard_path = getattr(settings, 'AUTOREPORTS_WIZARDFIELD', None)
        if not wizard_path:
            return WizardField
        return get_class_from_path(wizard_path)

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

    def render_api(self, modelfieldform, wizard):
        return self.render_admin(modelfieldform, wizard)

    def render_admin(self, modelfieldform, wizard):
        return "<div class='adaptor'>%s %s <h2 class='removeAdaptor'>%s</h2></div>" % (modelfieldform,
                                                                                       wizard,
                                                                                       _("Remove"))

    def render(self, form, model, is_admin=True):
        modelfieldform = self.render_model_field(form, model)
        wizard = self.render_wizard(is_admin)
        if is_admin:
            return self.render_admin(modelfieldform, wizard)
        return self.render_api(modelfieldform, wizard)

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

    def change_value(self, value, key, request_get):
        if len(value) <= 0 or not value[0]:
            del request_get[key]
        return (value, request_get)

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


class ProviderSelectSigle(object):

    slug_single = 'single'

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(),) + self.get_widgets_available_single()

    @classmethod
    def get_widgets_available_single(self):
        return (('single__select', _('Select')),
                ('single__radiobuttons', _('Radio buttons')))

    def get_change_filter(self, fil, opts):
        widget = self._get_widget_from_opts(opts)
        if widget and widget.startswith(self.slug_single):
            return ('exact', _('Exact'))
        return super(ProviderSelectSigle, self).get_change_filter(fil, opts)

    def change_widget_sigle(self, field, choices, widget):
        field_initial = field.initial and field.initial[0] or None
        field = forms.ChoiceField(label=field.label,
                                  choices=choices,
                                  help_text=field.help_text,
                                  initial=field_initial)
        if widget == 'single__radiobuttons':
            field.widget = forms.RadioSelect(choices=field.widget.choices)
        return field

    def change_widget(self, field, opts=None):
        widget = self._get_widget_from_opts(opts)
        choices = field.widget.choices
        choice_empty = [self.get_widgets_initial()]
        if isinstance(choices, list):
            new_choices = choice_empty + choices
        else:
            new_choices = itertools.chain(choice_empty, choices)
        if widget and widget.startswith(self.slug_single):
            field = self.change_widget_sigle(field, new_choices, widget)
        return field


class ProviderSelectMultiple(object):

    slug_multiple = 'multiple'

    @classmethod
    def get_widgets_available(self):
        return (self.get_widgets_initial(),) + self.get_widgets_available_multiple()

    @classmethod
    def get_widgets_available_multiple(self):
        return (('multiple__select', _('Select Multiple')),
                ('multiple__checkboxes', _('CheckBox Multiple')),)

    def get_change_filter(self, fil, opts):
        widget = self._get_widget_from_opts(opts)
        if widget and widget.startswith(self.slug_multiple):
            return ('in', _('In'))
        return super(ProviderSelectMultiple, self).get_change_filter(fil, opts)

    def change_widget_multiple(self, field, choices, widget):
        field = forms.MultipleChoiceField(label=field.label,
                                          choices=choices,
                                          help_text=field.help_text,
                                          initial=(field.initial,))
        if widget == 'multiple__checkboxes':
            field.widget = forms.CheckboxSelectMultiple(choices=choices)
        return field

    def change_widget(self, field, opts=None):
        widget = self._get_widget_from_opts(opts)
        choices = field.widget.choices
        if isinstance(choices, list):
            new_choices = choices
        else:
            new_choices = itertools.islice(choices, 1, None)
        if widget and widget.startswith(self.slug_multiple):
            field = self.change_widget_multiple(field, new_choices, widget)
        elif not widget:
            choice_empty = [self.get_widgets_initial()]
            if isinstance(choices, list):
                new_choices = choice_empty + choices
            else:
                new_choices = choices
            field.choices = new_choices
        return field


class ChoicesFieldReportField(ProviderSelectMultiple, TextFieldReportField):

    def get_value(self, obj, field_name=None):
        field_name = field_name or self.field_name_parsed
        choice_display = getattr(obj, 'get_%s_display' % field_name, None)
        if choice_display and callable(choice_display):
            return choice_display()
        return super(ChoicesFieldReportField, self).get_value(obj, field_name)

    def get_filter_default(self):
        return 'exact'

    def change_value(self, value, key, request_get):
        if not value[0]:
            del request_get[key]
        return (value, request_get)

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty')),)
                )

    def extra_wizard_fields(self):
        return super(TextFieldReportField, self).extra_wizard_fields()


class NumberFieldReportField(BaseReportField):

    def get_filter_default(self):
        return 'exact'

    def change_value(self, value, key, request_get):
        if value and len(value) > 0 and value[0].isnumeric():
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


class BaseDateFieldReportField(BaseReportField):

    def change_value_date_widget(self, value, key, request_get, field=None):
        if len(value) <= 0 or not value[0]:
            del request_get[key]
        if (key.endswith('__day') or
            key.endswith('__month') or
            key.endswith('__year')):
            return (self.parser_date(value, field), request_get)
        return ([unicode(self.parser_date(value, field))], request_get)

    def change_value_datetime_widget(self, value, key, request_get, field=None):
        if key.endswith('_0'):
            key_1 = key.replace('_0', '_1')
            if not key_1 in request_get:
                return value
            key_without_prefix = key.replace('_0', '')
            if request_get[key] and request_get[key_1]:
                value = "%s %s" % (request_get[key],
                                    request_get[key_1])
                value = [unicode(self.parser_date([value], field))]
                request_get.setlist(key_without_prefix, value)
            initial_date = 'initial-%s' % key_without_prefix
            if request_get.get(initial_date, None):
                del request_get['initial-%s' % key_without_prefix]
            del request_get[key]
            del request_get[key_1]
        return (value, request_get)


class DateFieldReportField(BaseDateFieldReportField):

    def get_filter_default(self):
        return 'exact'

    def change_widget(self, field, opts=None):
        field.widget = AdminDateWidget()
        return field

    def parser_date(self, value, field=None):
        try:
            field = field or self.field.formfield()
            return field.clean(value[0])
        except forms.ValidationError:
            return value

    def change_value(self, value, key, request_get):
        return self.change_value_date_widget(value, key, request_get)

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
        return (self.get_widgets_initial(), ('date', _('Date Widget')),)

    def change_widget(self, field, opts=None):
        widget = self._get_widget_from_opts(opts)
        if widget == 'date':
            field = forms.DateField(label=field.label,
                                    help_text=field.help_text)
            field.widget = AdminDateWidget()
        else:
            field.widget = AdminSplitDateTime()
        return field

    def change_value(self, value, key, request_get):
        if key.endswith('_0') or key.endswith('_1'):
            return self.change_value_datetime_widget(value, key, request_get, field=forms.DateTimeField())
        return self.change_value_date_widget(value, key, request_get, field=forms.DateField())


class BooleanFieldReportField(BaseReportField):

    def change_widget(self, field, opts=None):
        choices = (self.get_widgets_initial(),
                   ('0', _('No')),
                   ('1', _('Yes')),)

        field.widget = forms.Select(choices=choices)
        return field

    def change_value(self, value, key, request_get):
        if len(value) > 0:
            if value[0] == '0':
                return ([False], request_get)
            elif value[0] == '1':
                return ([True], request_get)
        if key in request_get:
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
        if is_iterable(value):
            if len(value) == 0:
                return None
            elif len(value) == 1:
                return value[0]
        return value

    def get_filter_default(self):
        return 'in'

    def change_value(self, value, key, request_get):
        if len(value) <= 0 or not value[0]:
            del request_get[key]
        return (value, request_get)

    @classmethod
    def get_filters(self):
        return (('in', _('In')),
                #('isnull', _('Is empty')),
               )


class RelatedReverseField(ProviderSelectSigle, RelatedReportField):

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


class ForeingKeyReportField(ProviderSelectMultiple, RelatedDirectField):

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty')),
               )

    def get_filter_default(self):
        return 'exact'

    def get_value(self, obj, field_name=None):
        try:
            return super(ForeingKeyReportField, self).get_value(obj, field_name)
        except ObjectDoesNotExist:
            return None  # Intigrity Error


class M2MReportField(ProviderSelectSigle, RelatedDirectField):

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
        except ImportError:
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
