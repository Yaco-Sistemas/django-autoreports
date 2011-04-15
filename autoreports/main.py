from django.contrib.admin.util import quote
from django.core.exceptions import ValidationError
from django.contrib.admin.views.main import ChangeList

from autoreports.utils import pre_procession_request
from cmsutils.adminfilters import QueryStringManager


class AutoReportChangeList(ChangeList):

    def __init__(self, request, model, prefix_url, *args, **kwargs):
        self.request = pre_procession_request(request, model)
        self.request_lite = pre_procession_request(request, model, lite=True)
        self.prefix_url = prefix_url
        super(AutoReportChangeList, self).__init__(self.request_lite, model, *args, **kwargs)

    def get_query_set(self):
        query_set = super(AutoReportChangeList, self).get_query_set()
        qsm = QueryStringManager(self.request)
        filters = qsm.get_filters()
        self._adavanced_filters = filters
        try:
            return query_set.filter(**filters).distinct()
        except ValidationError:
            return query_set

    def url_for_result(self, result):
        return "%s%s/" % (self.prefix_url, quote(getattr(result, self.pk_attname)))
