from django.contrib.admin.util import quote
from django.core.exceptions import ValidationError
from django.contrib.admin.views.main import ChangeList

from autoreports.utils import pre_procession_request, filtering_from_request


class AutoReportChangeList(ChangeList):

    def __init__(self, request, model, prefix_url, report, *args, **kwargs):
        self.request = pre_procession_request(request, model)
        self.request_lite = pre_procession_request(request, model, lite=True)
        self.prefix_url = prefix_url
        self.report = report
        super(AutoReportChangeList, self).__init__(self.request_lite, model, *args, **kwargs)

    def get_query_set(self):
        query_set = super(AutoReportChangeList, self).get_query_set()
        try:
            filters, query_set = filtering_from_request(self.request, query_set, report=self.report)
            self._adavanced_filters = filters
        except ValidationError:
            self._adavanced_filters = None
        return query_set

    def url_for_result(self, result):
        return "%s%s/" % (self.prefix_url, quote(getattr(result, self.pk_attname)))
