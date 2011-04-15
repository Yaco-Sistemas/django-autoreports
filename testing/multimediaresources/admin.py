from django.contrib import admin

from autoreports.admin import ReportAdmin

from multimediaresources.models import TypeResource, Resource, SetResource, ComputerResource


class TypeResourceAdmin(ReportAdmin, admin.ModelAdmin):
    pass


class ResourceAdmin(ReportAdmin, admin.ModelAdmin):
    list_display = ('name', 'created', 'resource_type', 'status', 'can_borrow')
    list_filter = ('status', 'resource_type')
    search_fields = ('name', )


class SetResourceAdmin(ReportAdmin, admin.ModelAdmin):
    pass


class ComputerResourceAdmin(ReportAdmin, admin.ModelAdmin):
    pass

admin.site.register(SetResource, SetResourceAdmin)
admin.site.register(ComputerResource, ComputerResourceAdmin)
admin.site.register(TypeResource, TypeResourceAdmin)
admin.site.register(Resource, ResourceAdmin)
