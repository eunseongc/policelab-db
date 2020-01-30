import os 

from django.contrib.gis import admin

from .models import Case, Video, Bookmark


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_expired', 'created_at']


@admin.register(Video)
class videoAdmin(admin.ModelAdmin):
    list_display = ['case_name', 'video_name', 'uploaded_at', 'rec_date', 'is_preprocessed']

    def case_name(self, obj):
        return obj.case.name

    def video_name(self, obj):
        return os.path.basename(str(obj.upload))


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['video_name', 'sec', 'code']

    def video_name(self, obj):
        return obj.video.name
