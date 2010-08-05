from django.utils.datastructures import SortedDict

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

    def get_registered_api(self):
        return self._registry.values()

    def get_api_class(self, key):
        return self._get_registration(key)

    def _get_registration(self, key):
        if key in self._registry:
            return self._registry[key]
        all_registered_keys = [k for k in self._registry]
        raise ReportNotRegistered(
            'Data provider %s not registered. Options are: %s'
            % (key, all_registered_keys),
        )

report_registry = ReportRegistry()
