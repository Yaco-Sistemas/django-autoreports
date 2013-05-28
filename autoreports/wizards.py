from django import forms
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.utils.translation import get_language
from django.utils.translation import ugettext
from django.utils.translation import ugettext_lazy as _

from autoreports.models import Report
from autoreports.utils import get_adaptor, parsed_field_name, get_field_by_name
from formadmin.forms import FormAdminDjango


class ReportNameForm(forms.ModelForm):

    prefixes = forms.CharField(label='',
                            widget=forms.HiddenInput,
                            required=False)

    def __init__(self, *args, **kwargs):
        super(ReportNameForm, self).__init__(*args, **kwargs)
        self.fields['name'].required = False

    def clean_prefixes(self):
        return self.cleaned_data.get('prefixes').split(', ')

    class Meta:
        model = Report
        fields = ('name', 'prefixes')


class ReportNameAdminForm(ReportNameForm, FormAdminDjango):

    def __unicode__(self):
        return self.as_django_admin()


class ModelFieldForm(forms.Form):

    def __init__(self, instance=None, *args, **kwargs):
        super(ModelFieldForm, self).__init__(*args, **kwargs)
        self.fields['app_label'] = forms.CharField(widget=forms.HiddenInput)
        self.fields['module_name'] = forms.CharField(widget=forms.HiddenInput)
        self.fields['field_name'] = forms.CharField(widget=forms.HiddenInput)

    def get_adaptor(self):
        app_label = self.cleaned_data.get('app_label')
        module_name = self.cleaned_data.get('module_name')
        field_name = self.cleaned_data.get('field_name')
        ct = ContentType.objects.get(app_label=app_label,
                                     model=module_name)
        model = ct.model_class()
        prefix, field_name_parsed = parsed_field_name(field_name)
        field_name, field = get_field_by_name(model, field_name_parsed)
        return get_adaptor(field)(model, field, field_name, treatment_transmeta=False)


class WizardField(forms.Form):

    def __init__(self, autoreport_field, instance=None, *args, **kwargs):
        super(WizardField, self).__init__(*args, **kwargs)
        self.autoreport_field = autoreport_field
        self.instance = instance
        self.fields['display'] = forms.BooleanField(label=_('Show in the report'), initial=True, required=False)
        autoreports_i18n = getattr(settings, 'AUTOREPORTS_I18N', False)
        lang = get_language()
        if autoreports_i18n:
            for lang_code, lang_text in settings.LANGUAGES:
                if not isinstance(lang_text, unicode):
                    lang_text = unicode(lang_text.decode('utf-8'))
                if lang_code == lang:
                    initial_label = autoreport_field.get_verbose_name()
                    initial_help_text = autoreport_field.get_help_text()
                else:
                    initial_label = ''
                    initial_help_text = ''
                self.fields['label_%s' % lang_code] = forms.CharField(label=u"%s %s" % (ugettext('label'), lang_text),
                                                    initial=initial_label,
                                                    required=False)
                self.fields['help_text_%s' % lang_code] = forms.CharField(label=u"%s %s" % (ugettext('Help Text'), lang_text),
                                                        initial=initial_help_text,
                                                        required=False)
        else:
            self.fields['label'] = forms.CharField(label=_('label'),
                                                initial=autoreport_field.get_verbose_name(),
                                                required=False)
            self.fields['help_text'] = forms.CharField(label=_('Help Text'),
                                                initial=autoreport_field.get_help_text(),
                                                required=False)
        filters = autoreport_field.get_filters()
        if filters:
            self.fields['filters'] = forms.MultipleChoiceField(label=_('Filters'),
                                                            initial=(autoreport_field.get_filter_default(),),
                                                            choices=filters,
                                                            widget=forms.CheckboxSelectMultiple,
                                                            required=False)
        widgets = autoreport_field.get_widgets_available()
        if widgets:
            self.fields['widget'] = forms.ChoiceField(label=_('Other widget'),
                                                      choices=widgets,
                                                      required=False,
                                                      help_text=_('Chose other widget. If you change the widget it\'s possible that the filter change also'))

        self.fields['order'] = forms.IntegerField(label=_('order'),
                                                 initial=0,
                                                 required=False)
        self.fields['order'].widget = forms.HiddenInput(attrs={'class': 'wizardOrder'})

        for key, field in autoreport_field.extra_wizard_fields().items():
            self.fields[key] = field

        if instance:
            field_name = autoreport_field.field_name
            field_options = instance.options.get(field_name)
            widget_initial = field_options.get('widget', None)
            if not field_options:
                return
            self.fields['display'].initial = field_options.get('display', False)
            self.fields['order'].initial = field_options.get('order', 0)
            if filters:
                self.fields['filters'].initial = field_options.get('filters', tuple())
            if widgets:
                self.fields['widget'].initial = widget_initial
            if autoreports_i18n:
                for lang_code, lang_text in settings.LANGUAGES:
                    label = 'label_%s' % lang_code
                    help_text = 'help_text_%s' % lang_code
                    self.fields[label].initial = field_options.get(label, '')
                    self.fields[help_text].initial = field_options.get(help_text, '')
            else:
                self.fields['label'].initial = field_options.get('label', '')
                self.fields['help_text'].initial = field_options.get('help_text', '')

    def __unicode__(self):
        return self.as_wizard_field()

    def as_render_default(self):
        return self.as_p()

    def as_wizard_field(self):
        verbose_name = self.autoreport_field.get_verbose_name()
        return render_to_string('autoreports/as_wizard_field.html',
                                {'verbose_name': verbose_name,
                                 'form': self})


class WizardAdminField(WizardField, FormAdminDjango):

    def __init__(self, autoreport_field, instance=None, *args, **kwargs):
        super(WizardAdminField, self).__init__(autoreport_field, instance, *args, **kwargs)
        self.fieldsets = ((self.autoreport_field.get_verbose_name(), {'fields': self.fields,
                                                                      'classes': ('collapsable', )},),)

    def __unicode__(self):
        return self.as_django_admin()
