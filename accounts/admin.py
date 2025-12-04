# accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Friendship

class CustomUserAdmin(UserAdmin):
    # Thêm các trường chỉnh sửa user
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('avatar', 'cover_photo', 'bio', 'birth_date')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('avatar', 'cover_photo', 'bio', 'birth_date')}),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(Friendship)