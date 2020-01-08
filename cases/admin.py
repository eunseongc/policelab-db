from django.contrib.gis import admin

from .models import Case, Video, Bookmark


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_expired', 'created_at']


@admin.register(Video)
class videoAdmin(admin.ModelAdmin):
    list_display = ['case_name', 'uploaded_at']

    def case_name(self, obj):
        return obj.case.name


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['video_name', 'sec', 'code']

    def video_name(self, obj):
        obj.video.name
