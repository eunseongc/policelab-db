from django.contrib import admin

from .models import Case
from .models import Video
from .models import Bookmark
# Register your models here.

admin.site.register(Case)
admin.site.register(Video)
admin.site.register(Bookmark)
