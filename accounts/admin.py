from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User
from rest_framework.authtoken.models import Token


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('email', 'is_staff', 'is_active', 'theme')
    list_filter = ('is_staff', 'is_active')

    ordering = ('email',)
    search_fields = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password', 'theme')}),
        ('Permissions', {
            'fields': (
                'is_staff',
                'is_active',
                'is_superuser',
                'groups',
                'user_permissions'
            )
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'password1',
                'password2',
                'is_staff',
                'is_active',
                'theme'
            )
        }),
    )


admin.site.register(User, CustomUserAdmin)
