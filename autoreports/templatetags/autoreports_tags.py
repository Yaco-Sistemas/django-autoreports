import re
from django import template

from cmsutils.adminfilters import QueryStringManager
from autoreports.admin import ReportAdmin

try:
    from merengue.adminsite import BaseAdminSite
    IN_MERENGUE = True
except:
    IN_MERENGUE = False

    class BaseAdminSite(object):
        pass

register = template.Library()


def autoreports_admin(context):
    context_tag = {}
    changelist = context.get('cl', None)
    model_admin = getattr(changelist, 'model_admin', None)
    if model_admin:
        context_tag['module'] = model_admin.__module__
        context_tag['class_name'] = model_admin.__class__.__name__
        context_tag['app_label'] = model_admin.model._meta.app_label
        context_tag['module_name'] = model_admin.model._meta.module_name

        qsm = QueryStringManager(context.get('request'))
        query_string = qsm.get_query_string()
        related_field = getattr(model_admin, 'related_field', None)
        object_owner = _object_owner(context.get('request'), model_admin)
        if related_field and object_owner:
            if query_string == '?':
                query_string_extra = ''
            else:
                query_string_extra = '&'
            query_string_extra += '%s=%s' %(related_field, object_owner.pk)
            query_string += query_string_extra
        context_tag['query_string'] = query_string
    return context_tag
autoreports_admin = register.inclusion_tag('autoreports/autoreports_admin.html', takes_context=True)(autoreports_admin)


def _object_owner(request, model_admin):
    admin_site = model_admin.admin_site
    if IN_MERENGUE and isinstance(admin_site, BaseAdminSite):
        next = admin_site.base_tools_model_admins.get(getattr(model_admin, 'tool_name', None), None)
        if next:
            object_id = admin_site.base_object_ids.get(getattr(model_admin, 'tool_name', None), None)
            return next._get_base_content(request, object_id, next)
    return None


class IsSonOfReportAdminNode(template.Node):

    def __init__(self, var_name):
        self.var_name = var_name

    def render(self, context):
        admin =__import__(context.get('module', ''), {}, {}, context.get('class_name', ''))
        model_admin = getattr(admin, context.get('class_name', ''), None)
        context[self.var_name] = issubclass(model_admin, ReportAdmin)
        return ''


@register.tag
def is_son_of_report_admin(parser, token):
    try:
        tag_name, arg = token.contents.split(None, 1)
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires arguments" % token.contents.split()[0]
    m = re.search(r'as ([\w_-]+)', arg)
    if not m:
        raise template.TemplateSyntaxError, "%r tag needs an 'as variable_name' parameters" % tag_name
    return IsSonOfReportAdminNode(m.group(1))
