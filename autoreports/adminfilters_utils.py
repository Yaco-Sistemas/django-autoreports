import re
import urllib

from django.conf import settings
from django.utils.encoding import smart_str
from django.utils.safestring import mark_safe
from django.contrib.admin.views.main import ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, SEARCH_VAR

# The maximum number of items to display in a QuerySet.__repr__
REPR_OUTPUT_SIZE = 20


class QuerySetWrapper(object):
    """Wrapper class that allows to use a list of objects where a queryset
    is expected (e.g. django.views.generic.list_detail.object_list)
    """
    def __init__(self, data):
        self.data = data
        if self.data:
            self.model = self.data[0].__class__

    def __repr__(self):
        data = list(self[:REPR_OUTPUT_SIZE + 1])
        if len(data) > REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."
        return repr(data)

    def _clone(self):
        return QuerySetWrapper(self.data)

    def __len__(self):
        return len(self.data)

    def count(self):
        return len(self.data)

    def __getitem__(self, k):
        return self.data[k]

    def __getslice__(self, i, j):
        return self.data[i:j]

    def __iter__(self):
        return iter(self.data)


def get_lookup_params(request, remove=[]):
    """ get lookup params from a http request query param1=value1&param2__lt=value2&... """
    lookup_params = dict(request.REQUEST.items()).copy() # a dictionary of the query string
    excluded_params = [ALL_VAR, ORDER_VAR, ORDER_TYPE_VAR, SEARCH_VAR]
    excluded_params.extend(remove)
    for i in excluded_params:
        if i in lookup_params:
            del lookup_params[i]
    for key, value in lookup_params.items():
        if not isinstance(key, str):
            del lookup_params[key]
            lookup_params[smart_str(key)] = value
    return lookup_params


def get_query_string(request, lookup_params=None, remove=None):
    """ get http query string from lookup params like {'param1':'value1', 'param2__lt':'value2' """
    if lookup_params is None: lookup_params = {}
    if remove is None: remove = []
    params = dict(request.GET.iterlists()).copy()
    for r in remove:
        for k in params.keys():
            if k.startswith(r):
                del params[k]
    for k, v in lookup_params.items():
        if k in params and v is None:
            del params[k]
        elif v is not None:
            params[k] = [v]
    query_string = '?'
    for k, values in params.items():
        print k
        for v in values:
            if query_string != '?':
                query_string += '&'
            query_string += u'%s=%s' % (k, v)
    return mark_safe(query_string.replace(' ', '%20'))


def encrypt(cad, key=None):
    from Crypto.Hash import MD5
    from Crypto.Cipher import AES

    if not key:
        key = settings.SECRET_KEY
        assert (isinstance(cad, unicode)), "cad must be an unicode string."
    else:
        assert (isinstance(cad, unicode) and isinstance(key, unicode)), "cad and key must be unicode strings."
    md5 = MD5.new()
    md5.update(key)
    hash_key = md5.hexdigest()
    cipher = AES.new(hash_key, AES.MODE_ECB)
    cipher_len = 16
    cad_latin = cad.encode("latin1")
    cad_ascii = urllib.pathname2url(cad_latin)
    mod = len(cad_ascii) % cipher_len
    padding = (cipher_len - int(mod) - 1)
    cad_padding = cad_ascii + ('0' * padding) + hex(padding)[-1:]
    cipher_cad = cipher.encrypt(cad_padding)
    cipher_unicode = unicode(cipher_cad, "latin1")
    cipher_byte =   u''.join([u'\\%03o' % ord(c) for c in cipher_unicode])
    return cipher_unicode and cipher_byte


def decrypt(cipher_unicode, key=None):
    from Crypto.Hash import MD5
    from Crypto.Cipher import AES

    if not key:
        key = settings.SECRET_KEY
        assert (isinstance(cipher_unicode, unicode)), "cipher_unicode must be an unicode string."
    else:
        assert (isinstance(cipher_unicode, unicode) and isinstance(key, unicode)), "cipher_unicode and key must be unicode strings."
    md5 = MD5.new()
    md5.update(key)
    hash_key = md5.hexdigest()
    cipher = AES.new(hash_key, AES.MODE_ECB)
    cipher_len = 16
    cipher_byte = unicode(''.join([chr(int(c, 8)) for c in cipher_unicode.split('\\')[1:]]), "latin1")
    cipher_cad = cipher_byte.encode("latin1")
    cad_padding = cipher.decrypt(cipher_cad)
    padding = int("0x%s" % cad_padding[-1:], 16) + 1
    cad_ascii = urllib.url2pathname(cad_padding[:-padding])
    cad_latin = cad_ascii.decode("latin1")
    cad = unicode(cad_latin)
    return cad


def is_encrypted(value):
    return bool(re.match(r'(\\\d+)+$', value))