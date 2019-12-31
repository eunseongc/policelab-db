from django.contrib import admin

from .models import Members
from .models import Cases
from .models import Membercases
from .models import Videos
from .models import Marks
# Register your models here.

admin.site.register(Member)
admin.site.register(Case)
admin.site.register(Membercase)
admin.site.register(Video)
admin.site.register(Mark)
