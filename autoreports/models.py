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

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.forms.models import ModelFormMetaclass, get_declared_fields, media_property, ModelFormOptions, ModelForm
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext_lazy as _


def modelform_factory(model, form=ModelForm, fields=None, exclude=None,
                       formfield_callback=lambda f: f.formfield()):
    # Create the inner Meta class. FIXME: ideally, we should be able to
    # construct a ModelForm without creating and passing in a temporary
    # inner class.

    # Build up a list of attributes that the Meta object will have.
    attrs = {'model': model}
    if fields is not None:
        attrs['fields'] = fields
    if exclude is not None:
        attrs['exclude'] = exclude

    # If parent form class already has an inner Meta, the Meta we're
    # creating needs to inherit from the parent's inner meta.
    parent = (object, )
    if hasattr(form, 'Meta'):
        parent = (form.Meta, object)
    Meta = type('Meta', parent, attrs)

    # Give this new form class a reasonable name.
    class_name = model.__name__ + 'Form'

    # Class attributes for the new form class.
    form_class_attrs = {
        'Meta': Meta,
        'formfield_callback': formfield_callback,
    }
    return form.__metaclass__(class_name, (form, ), form_class_attrs)


def fields_for_model(model, fields=None, exclude=None, formfield_callback=lambda f: f.formfield()):
    """
    Returns a ``SortedDict`` containing form fields for the given model.

    ``fields`` is an optional list of field names. If provided, only the named
    fields will be included in the returned fields.

    ``exclude`` is an optional list of field names. If provided, the named
    fields will be excluded from the returned fields, even if they are listed
    in the ``fields`` argument.
    """
    field_list = []
    ignored = []
    opts = model._meta
    for f in opts.fields + opts.many_to_many:
        if fields and not f.name in fields:
            continue
        if exclude and f.name in exclude:
            continue
        formfield = formfield_callback(f)
        if formfield:
            field_list.append((f.name, formfield))
        else:
            ignored.append(f.name)
    field_dict = SortedDict(field_list)
    if fields:
        field_dict = SortedDict(
            [(f, field_dict.get(f)) for f in fields
                if ((not exclude) or (exclude and f not in exclude)) and (f not in ignored)])
    return field_dict


class ReportModelFormMetaclass(ModelFormMetaclass):

    def __new__(cls, name, bases, attrs):
        formfield_callback = attrs.pop('formfield_callback',
                lambda f: f.formfield())
        try:
            parents = [b for b in bases if issubclass(b, ModelForm)]
        except NameError:
            # We are defining ModelForm itself.
            parents = None
        declared_fields = get_declared_fields(bases, attrs, False)
        new_class = super(ModelFormMetaclass, cls).__new__(cls, name, bases,
                attrs)
        if not parents:
            return new_class

        if 'media' not in attrs:
            new_class.media = media_property(new_class)
        opts = new_class._meta = ModelFormOptions(getattr(new_class, 'Meta', None))
        if opts.model:
            # If a model is defined, extract form fields from it.
            fields = fields_for_model(opts.model, opts.fields,
                                      opts.exclude, formfield_callback)
            # Override default model fields with any custom declared ones
            # (plus, include all the other declared fields).
            fields.update(declared_fields)
        else:
            fields = declared_fields
        new_class.declared_fields = declared_fields
        new_class.base_fields = fields
        return new_class


class BaseReport(models.Model):
    name = models.CharField(_('Name'), max_length=200)
    report_filter_fields = models.TextField(_('Report filter fields'), null=True, blank=True)
    report_display_fields = models.TextField(_('Report display fields'), null=True, blank=True)
    advanced_options = models.TextField(_('advanced_options'), null=True, blank=True)
    content_type = models.ForeignKey(ContentType, verbose_name=_('Content type'))

    @property
    def report_filter_fields_tuple(self):
        if self.report_filter_fields:
            return tuple(self.report_filter_fields.split(', '))
        return tuple()

    @property
    def report_display_fields_tuple(self):
        if self.report_display_fields:
            return tuple(self.report_display_fields.split(', '))
        return tuple()

    @classmethod
    def get_colums_wizard(cls):
        return {'fields': True,
                'filter': True,
                'display': True,
                'help_text': True,
                'advanced_options': True}

    class Meta:
        verbose_name = _('base report')
        verbose_name_plural = _('base reports')
        abstract = True

    def __unicode__(self):
        return self.name


class Report(BaseReport):

    class Meta:
        verbose_name = _('report')
        verbose_name_plural = _('reports')
