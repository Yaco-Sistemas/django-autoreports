from django.contrib.sites.models import Site


def add_domain(value):
    site = Site.objects.get_current()
    value = 'http://%s%s' %(site.domain, value)
    return value
