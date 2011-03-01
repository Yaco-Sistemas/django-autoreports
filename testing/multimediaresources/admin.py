from django.contrib import admin

from autoreports.admin import ReportAdmin

from multimediaresources.models import TypeResource, Resource


class TypeResourceAdmin(ReportAdmin, admin.ModelAdmin):
    pass


class ResourceAdmin(ReportAdmin, admin.ModelAdmin):
    pass


admin.site.register(TypeResource, TypeResourceAdmin)
admin.site.register(Resource, ResourceAdmin)
