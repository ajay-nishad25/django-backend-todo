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

    due_date = serializers.DateField(
        required=False,
        allow_null=True
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
    
    def update(self, instance, validated_data):
        tag_id = validated_data.pop("tag_id", None)

        # Update normal fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Handle tag update (optional)
        if tag_id is not None:
            if tag_id == "":
                instance.tag = None
            else:
                try:
                    instance.tag = Tag.objects.get(tag_code=tag_id)
                except Tag.DoesNotExist:
                    raise serializers.ValidationError(
                        {"tag_id": "Invalid tag"}
                    )

        instance.save()
        return instance

