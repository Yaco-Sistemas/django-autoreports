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

from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext_lazy as _

from autoreports.api import ReportApi


class ReportNotRegistered(Exception):
    pass


class ReportRegistry(object):

    def __init__(self):
        self._registry = SortedDict({})

    def register_api(self, model_class, model_api=None, key=None):
        if not key:
            if model_api:
                key = model_api.__name__.lower()
            else:
                key = "%s_%s" % (model_class._meta.app_label,
                                model_class._meta.module_name)
        if self.is_registered(key):
            raise ValueError('Another api is already registered '
                             'with the key %s' % model_class)

        model_api = model_api or ReportApi
        self._registry[key] = model_api(model_class)

    def is_registered(self, key):
        try:
            self.get_api_class(key)
        except ReportNotRegistered:
            return False
        else:
            return True

    def get_registered(self):
        return self._registry

    def get_categories(self):
        categories = []
        for key, value in self._registry.items():
            if getattr(value, 'category', None):
                category_key = value.category
                verbose_category = getattr(value, 'category_verbosename', value.category)
            else:
                category_key = 'no_category'
                verbose_category = _('No category')
            categories.append(category_key)
        return list(set(categories))

    def get_registered_for_category(self, category=None):
        registry_category = {}
        for key, value in self._registry.items():
            if getattr(value, 'category', None):
                category_key = value.category
                verbose_category = getattr(value, 'category_verbosename', value.category)
            else:
                category_key = 'no_category'
                verbose_category = _('No category')
            if category and category != category_key:
                continue
            if not category_key in registry_category:
                registry_category[category_key] = {'list': {}, 'category_verbosename': verbose_category}
            registry_category[category_key]['list'][key] = value
        return registry_category

    def get_registered_keys(self):
        return self._registry.keys()

    def get_registered_api(self):
        return self._registry.values()

    def get_api_class(self, key):
        return self._get_registration(key)

    def _get_registration(self, key):
        if key in self._registry:
            return self._registry[key]
        all_registered_keys = [k for k in self._registry]
        raise ReportNotRegistered(
            'Registry provider %s not registered. Options are: %s'
            % (key, all_registered_keys),
        )

report_registry = ReportRegistry()
