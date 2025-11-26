from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Task, TaskAssignment, TaskComment, TaskHistory


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для User"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class TaskCommentSerializer(serializers.ModelSerializer):
    """Сериализатор для комментариев"""
    author = UserSerializer(read_only=True)

    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'content', 'is_edited', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']


class TaskHistorySerializer(serializers.ModelSerializer):
    """Сериализатор для истории изменений"""
    changed_by = UserSerializer(read_only=True)

    class Meta:
        model = TaskHistory
        fields = ['id', 'task', 'changed_by', 'field_name', 'old_value', 'new_value', 'changed_at']
        read_only_fields = ['id', 'changed_by', 'changed_at']


class TaskAssignmentSerializer(serializers.ModelSerializer):
    """Сериализатор для назначения задач"""
    user = UserSerializer(read_only=True)
    assigned_by = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TaskAssignment
        fields = ['id', 'task', 'user', 'user_id', 'assigned_by', 'role', 'status', 'assigned_at', 'notes']
        read_only_fields = ['id', 'assigned_by', 'assigned_at']

    def create(self, validated_data):
        """Автоматически установить assigned_by в текущего пользователя"""
        validated_data['assigned_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка задач (краткая информация)"""
    created_by = UserSerializer(read_only=True)
    comment_count = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ['id', 'title', 'status', 'priority', 'created_by', 'due_date',
                  'created_at', 'updated_at', 'comment_count', 'participant_count']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def get_comment_count(self, obj):
        return obj.comments.count()

    def get_participant_count(self, obj):
        return obj.assignments.count()


class TaskDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детального вида задачи"""
    created_by = UserSerializer(read_only=True)
    assignments = TaskAssignmentSerializer(many=True, read_only=True)
    comments = TaskCommentSerializer(many=True, read_only=True)
    history = TaskHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'status', 'priority', 'created_by',
                  'due_date', 'created_at', 'updated_at', 'is_deleted',
                  'assignments', 'comments', 'history']
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at',
                           'assignments', 'comments', 'history']

    def create(self, validated_data):
        """Автоматически установить created_by в текущего пользователя"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления задач"""
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'status', 'priority', 'due_date', 'created_by']
        read_only_fields = ['id', 'created_by']

    def create(self, validated_data):
        """Автоматически установить created_by в текущего пользователя"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate_status(self, value):
        """Валидация статуса при создании"""
        if value not in ['pending', 'in_progress', 'completed', 'cancelled']:
            raise serializers.ValidationError(f"Неверный статус: {value}")
        return value

    def validate_priority(self, value):
        """Валидация приоритета"""
        if value not in ['low', 'medium', 'high', 'urgent']:
            raise serializers.ValidationError(f"Неверный приоритет: {value}")
        return value
