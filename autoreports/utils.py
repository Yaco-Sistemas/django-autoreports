from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from autoreports import csv_to_excel

EXPORT_FORMATS = {
    'csv': {
        'file_extension': 'csv',
        'label': _('Report to CSV'),
    },
    'excel': {
        'file_extension': 'xls',
        'label': _('Report to Excel'),
    },
}


def add_domain(value):
    site = Site.objects.get_current()
    value = 'http://%s%s' %(site.domain, value)
    return value


def get_available_formats():
    formats = {}
    for format, format_data in EXPORT_FORMATS.items():
        if format == 'excel' and not csv_to_excel.HAS_PYEXCELERATOR:
            continue
        formats[format] = format_data
    return formats
