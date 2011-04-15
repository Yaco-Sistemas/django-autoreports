from django.contrib.admin.filterspecs import FilterSpec, RelatedFilterSpec
from django.core.exceptions import FieldError
from django.http import Http404
from django.utils.datastructures import MultiValueDict
from django.utils.safestring import mark_safe
from django.utils.encoding import smart_unicode
from django.utils.translation import ugettext as _

from autoreports.adminfilters_utils import QuerySetWrapper


IN_LOOKUP = '__in'
PAGE_VAR = 'p'


def filter_by_query_string(request, queryset, page_var=PAGE_VAR,
                           search_fields=[], none_if_empty=False,
                           ignore_params=[]):
    qsm = QueryStringManager(request, search_fields, page_var, ignore_params)
    filters = qsm.get_filters()
    excluders = qsm.get_excluders()
    if filters or excluders:
        try:
            queryset = queryset.filter(**filters)
            queryset = queryset.exclude(**excluders)
        except FieldError, e:
            raise Http404
    elif none_if_empty:
        queryset = queryset.none()
    return queryset, qsm


class QueryStringManager(object):
    """
    QueryStringManager can be used to automatically set filters on listing.

    We take idea from django.contrib.admin.views.main.ChangeList class, but without all
    admin functionality (less coupled principle)

    However, it implements foofield__id__in filters, for example, equivalent to:

    FooModel.objects.filter(category__id__in=[8,9])

    Example of use, with a request like http://foo.com?category__id__in=9&category__id__in=8:

    >>> qsm = QueryStringManager(request)
    >>> qsm.get_params()
    <MultiValueDict: {'category__id__in': [u'9', u'8']}>
    >>> qsm.get_query_string()
    u'?category__id__in=9&amp;category__id__in=8'
    >>> qsm.get_filters()
    <MultiValueDict: {'category__id__in': [u'9', u'8']}>

    You can then use it in a view with:

    def foo_listing(request, ...):
      qsm = QueryStringManager(request)
      queryset = FooModel.objects.all()
      queryset = queryset.filter(qsm.get_filters())
      category_choices = Category.objects.filter(parent__isnull=True)
      render_to_response('foo_listing.html', {'queryset': queryset,
                                              'qsm': qsm,
                                              'category_choices': category_choices} )

    And last, in template you can use cmsutils admin filters with:

    {% load modelfilters %}
    {% filter_for_model 'fooapp' 'foomodel' 'publish_date' %}
    {% filter_for_model 'fooapp' 'foomodel' 'category' category_choices %}
    """

    def __init__(self, request, search_fields=[], page_var=PAGE_VAR, ignore_params=[]):
        self.params = MultiValueDict()
        self.filters = MultiValueDict()
        self.excluders = MultiValueDict()
        self.search_fields = MultiValueDict()
        self.page=None

        if request is None:
            return

        raw_filters = {}
        for key, l in request.GET.lists():
            if key == page_var:
                self.page = l
            elif key.startswith('__') or key in ignore_params: # private arg
                continue
            elif key.endswith('_0') or key.endswith('_1'):
                if key.endswith('_0'):
                    key_new, l_new = self._convert_filter_splitdatetime(request, key, l, '_0', raw_filters)
                elif key.endswith('_1'):
                    key_new, l_new = self._convert_filter_splitdatetime(request, key, l, '_1', raw_filters)

                raw_filters[key_new] = l_new
            else:
                raw_filters[key] = l

        for key, l in raw_filters.items():
            try:
                key = str(key)
            except UnicodeEncodeError:
                key = 'key_%s' % len(l)
            self._set_into_dict(self.params, key, l)
            if key in search_fields:
                self._set_into_dict(self.search_fields, key, l)
            elif u'not_' in key:
                self._set_into_dict(self.excluders, key, l)
            else:
                self._set_into_dict(self.filters, key, l)

    def _get_from_dict(self, multidict, key):
        if key.endswith(IN_LOOKUP):
            return multidict.getlist(str(key))
        else:
            return multidict.get(str(key))

    def _set_into_dict(self, multidict, key, value):
        if key.endswith(IN_LOOKUP):
            multidict.setlist(str(key), value)
        else:
            multidict[str(key)] = value[0]

    def _get_multidict_items(self, multidict):
        for k, l in multidict.lists():
            for v in l:
                yield k, v

    def _convert_filter_splitdatetime(self, request, key, l, endswith, filters):
        key_new = key.replace(endswith, '')
        date = request.GET.get('%s_0' % key_new, '')
        hour = request.GET.get('%s_1' % key_new, '')
        if date and hour:
            value_new = '%s %s' %(date, hour)
            value_new = value_new.strip()
            return (key_new, [value_new])
        return key, l

    def get_query_string(self, new_params=None, remove=None):
        if new_params is None: new_params = MultiValueDict()
        if remove is None: remove = []
        p = self.params.copy()
        for r in remove:
            for k in p.keys():
                if (k.startswith(r) and r.endswith('__')) or k==r:
                    del p[k]
        if isinstance(new_params, MultiValueDict):
            new_params_items = new_params.lists()
            setter = p.setlist
        else:
            new_params_items = new_params.items()
            setter = p.__setitem__
        for k, v in new_params_items:
            if k in p and v is None:
                del p[k]
            elif v is not None:
                setter(k, v)
        query_string_blocks = []
        for k, l in p.lists():
            query_string_blocks.append('&'.join([u'%s=%s' % (k, v) for v in l]))
        return mark_safe('?' + '&'.join(query_string_blocks).replace(' ', '%20'))

    def get_params(self):
        return self.params

    def get_params_items(self):
        return self._get_multidict_items(self.params)

    def get_search_fields(self):
        return self.search_fields

    def get_filters(self):
        filters = {}
        for key in self.filters.keys():
            filters[key] = self._get_from_dict(self.filters, key)
        return filters

    def get_excluders(self):
        excluders = {}
        for key in self.excluders.keys():
            filter_key = key.replace('not_', '')
            excluders[filter_key] = self._get_from_dict(self.excluders, key)
        return excluders

    def get_filters_items(self):
        return self._get_multidict_items(self.filters)

    def get_search_value(self, value):
        return self.search_fields.get(value, None)

    def get_page(self):
        return self.page

    def search_performed(self):
        return bool(self.filters) or bool(self.excluders) or bool(self.search_fields)


class FieldAvailabilityValueFilterSpec(FilterSpec):
    def __init__(self, f, request, params, model, model_admin):
        super(FieldAvailabilityValueFilterSpec, self).__init__(f, request, params, model, model_admin)
        self.lookup_kwarg = '%s__isnull' % f.name
        self.lookup_val = request.GET.get(self.lookup_kwarg, None)

    def title(self):
        return _('availability of %s') % self.field.verbose_name

    def choices(self, cl):
        for k, v in ((_('Indistinct'), None), (_('Yes'), ''), (_('No'), 'True')):
            yield {'selected': self.lookup_val == v,
                   'query_string': cl.get_query_string({self.lookup_kwarg: v}),
                   'display': k}


class MultipleRelatedFilterSpec(RelatedFilterSpec):
    """
    FilterSpec encapsulates the logic for displaying filters in the Django admin.
    Filters are specified in models with the "list_filter" option.

    MultipleRelatedFilterSpec can specify foofield__id__in=[1,2,3] filters.
    It depends on use of MultiQueryStringManager to work.

    """
    def __init__(self, f, request, params, model, model_admin, choices_queryset=None):
        super(MultipleRelatedFilterSpec, self).__init__(f, request, params, model, model_admin)
        self.lookup_kwarg = '%s__%s__in' % (f.name, f.rel.to._meta.pk.name)
        self.lookup_val = request.GET.getlist(self.lookup_kwarg)
        if choices_queryset is not None:
            self.lookup_choices = choices_queryset
        else:
            self.lookup_choices = f.rel.to._default_manager.all()

    def title(self):
        return self.field.verbose_name

    def choices(self, cl):
        yield {'selected': self.lookup_val is None,
               'query_string': cl.get_query_string({}, [self.lookup_kwarg]),
               'display': _('All')}
        for val in self.lookup_choices:
            pk_val = getattr(val, self.field.rel.to._meta.pk.attname)
            params = cl.get_params().copy()
            if not params.has_key(self.lookup_kwarg):
                params.setlist(self.lookup_kwarg, [pk_val])
            else:
                lookup_values = params.getlist(self.lookup_kwarg) + list([unicode(pk_val)])
                params.setlist(self.lookup_kwarg, lookup_values)
            query_string = cl.get_query_string(params)
            yield {'selected': smart_unicode(pk_val) in self.lookup_val,
                   'query_string': query_string,
                   'display': val}

