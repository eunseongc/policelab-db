from django.contrib import admin

from .models import Members
from .models import Cases
from .models import Membercases
from .models import Videos
from .models import Marks
# Register your models here.


class MemberAdmin(admin.ModelAdmin):
    list_display = []


admin.site.register(Members)
admin.site.register(Cases)
admin.site.register(Membercases)
admin.site.register(Videos)
admin.site.register(Marks)
