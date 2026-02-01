from rest_framework import serializers
from .models import Todo, Tag


class TodoSerializer(serializers.ModelSerializer):
    tag_id = serializers.IntegerField(
        required=False,
        write_only=True
    )

    tag = serializers.CharField(
        source="tag.name",
        read_only=True
    )

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "is_completed",
            "is_archived",
            "due_date",
            "tag",
            "tag_id",
            "created_at"
        ]

    def create(self, validated_data):
        tag_id = validated_data.pop("tag_id", None)

        todo = Todo(**validated_data)

        if tag_id:
            try:
                todo.tag = Tag.objects.get(id=tag_id)  # ✅ FIX HERE
            except Tag.DoesNotExist:
                raise serializers.ValidationError(
                    {"tag_id": "Invalid tag"}
                )

        todo.save()
        return todo
