from django.contrib import admin
from .models import Todo, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Todo)
class TodoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "user",
        "tag",
        "is_archived",
        "due_date",
        "created_at",
    )
    list_filter = ("is_archived", "tag")
    search_fields = ("title", "description", "user__email")
