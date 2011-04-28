import collections

from copy import copy

from django.conf import settings
from django.contrib.admin.widgets import AdminSplitDateTime, AdminDateWidget
from django.db.models import ObjectDoesNotExist
from django.forms import Select, TextInput, IntegerField, ValidationError, ModelMultipleChoiceField
from django.utils.translation import get_language
from django.utils.translation import ugettext as _

from autoreports.forms import BaseReportForm
from autoreports.model_forms import modelform_factory
from autoreports.utils import get_field_from_model, parsed_field_name, transmeta_field_name, SEPARATED_FIELD
from autoreports.wizards import ModelFieldForm, WizardField, WizardAdminField


class BaseReportField(object):

    def __init__(self, model, field, field_name=None, instance=None, *args, **kwargs):
        super(BaseReportField, self).__init__(*args, **kwargs)
        self.model = model
        self.field = field
        self.field_name = field_name or self.field.name
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

    def render(self, form, model, is_admin=True):
        modelfieldform = ModelFieldForm(initial={'app_label': model._meta.app_label,
                                                 'module_name': model._meta.module_name,
                                                 'field_name': self.field_name},
                                        instance=self.instance,
                                        prefix=form.prefix)

        wizard = self.get_form(is_admin)
        if is_admin:
            return "<div class='adaptor'>%s %s <h2 class='removeAdaptor'>%s</h2></div>" % (unicode(modelfieldform),
                                                                                           unicode(wizard),
                                                                                           _("Remove"))
        return "%s %s" % (unicode(modelfieldform), unicode(wizard))

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

    def get_filter_default(self):
        return 'icontains'

    def change_widget(self, field, opts=None):
        field.widget = TextInput()
        return field

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


class ChoicesFieldReportField(TextFieldReportField):

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
        return (value, request_get)

    @classmethod
    def get_filters(self):
        return (('exact', _('Exact')),
                #('isnull', _('Is empty')),)
                )

    def change_widget(self, field, opts=None):
        field.widget.choices = [('', '----')] + field.widget.choices
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
        return IntegerField(label=self.get_verbose_name())


class DateFieldReportField(BaseReportField):

    def get_filter_default(self):
        return 'exact'

    def change_widget(self, field, opts=None):
        field.widget = AdminDateWidget()
        return field

    def parser_date(self, value):
        try:
            return self.field.formfield().clean(value)
        except ValidationError:
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

        field.widget = Select(choices=choices)
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

    def get_basic_field_form(self, form, field_name):
        return ModelMultipleChoiceField(label=self.get_verbose_name(),
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
        prefix, field_name = parsed_field_name(self.field_name)
        return field_name

    def get_help_text(self):
        return ''

    def get_value(self, obj, field_name=None):
        value = super(FuncField, self).get_value(obj, field_name)()
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
