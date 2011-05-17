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
from django.utils.translation import ugettext_lazy as _

from configfield.dbfields import JSONField
from south.modelsinspector import add_introspection_rules


class BaseReport(models.Model):
    name = models.CharField(_('Name'), max_length=200)
    content_type = models.ForeignKey(ContentType, verbose_name=_('Content type'))
    options = JSONField(blank=True, null=True)
    # Format: {'field_name': {'filters': ['subfix1', 'subfix2'],
                              #'display': true,
                              #'initial': true,
                              #'label': 'label 1',
                              #'help text: '****',
                              #'other_fields': [],
                              #'widget': 'Select'}},}

    @property
    def report_filter_fields_tuple(self):
        report_filter = []
        if self.options:
            for field_name, opts in self.options.items():
                for fil in self.options[field_name].get('filters', []):
                    report_filter.append("%s__%s" % (field_name, fil))
        return tuple(report_filter)

    @property
    def report_display_fields_tuple(self):
        if self.options:
            return tuple([field_name for field_name in self.options if self.options[field_name].get('display', False)])
        return tuple()

    class Meta:
        verbose_name = _('base report')
        verbose_name_plural = _('base reports')
        abstract = True

    def __unicode__(self):
        return self.name


class Report(BaseReport):

    def get_redirect_wizard(self, report=None):
        if report:
            return '../../%s' % self.id
        else:
            return '../%s' % self.id

    class Meta:
        verbose_name = _('report')
        verbose_name_plural = _('reports')


# ----- adding south rules to help introspection -----
rules_jsonfield = [
  (
    (JSONField, ),
    [],
    {},
  ),
]

add_introspection_rules(rules_jsonfield, ["^autoreports"])
