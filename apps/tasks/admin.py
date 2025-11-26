from django.contrib import admin
from django.utils.html import format_html
from .models import Task, TaskAssignment, TaskComment, TaskHistory


class TaskAssignmentInline(admin.TabularInline):
    """Inline admin для быстрого назначения исполнителей"""
    model = TaskAssignment
    extra = 1
    fields = ['user', 'role', 'status', 'notes', 'assigned_by']
    readonly_fields = ['assigned_by']

    def save_formset(self, request, form, formset, change):
        """Автоматически установить assigned_by в текущего пользователя"""
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.assigned_by_id:
                instance.assigned_by = request.user
        formset.save()


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'status_colored', 'priority', 'created_by', 'due_date', 'created_at', 'is_deleted']
    list_filter = ['status', 'priority', 'created_at', 'is_deleted']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('id', 'title', 'description')
        }),
        ('Статус и приоритет', {
            'fields': ('status', 'priority')
        }),
        ('Назначение', {
            'fields': ('created_by',)
        }),
        ('Даты', {
            'fields': ('due_date', 'created_at', 'updated_at')
        }),
        ('Удаление', {
            'fields': ('is_deleted',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Автоматически установить created_by если это новая задача"""
        if not change:  # Если это создание новой задачи
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def status_colored(self, obj):
        colors = {
            'pending': '#FFA500',
            'in_progress': '#0066CC',
            'completed': '#00CC00',
            'cancelled': '#CC0000',
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_colored.short_description = 'Статус'

    def get_queryset(self, request):
        """По умолчанию показывать только активные, но админ может видеть все"""
        qs = Task.all_objects.all()
        return qs


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'role', 'status', 'assigned_by', 'assigned_at']
    list_filter = ['role', 'status', 'assigned_at']
    search_fields = ['task__title', 'user__username']
    readonly_fields = ['id', 'assigned_at', 'updated_at']
    fieldsets = (
        ('Задача и пользователь', {
            'fields': ('id', 'task', 'user')
        }),
        ('Назначение', {
            'fields': ('assigned_by', 'role', 'status')
        }),
        ('Примечания', {
            'fields': ('notes',)
        }),
        ('Даты', {
            'fields': ('assigned_at', 'updated_at')
        }),
    )


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'author', 'created_at', 'is_edited']
    list_filter = ['created_at', 'is_edited']
    search_fields = ['task__title', 'author__username', 'content']
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Информация', {
            'fields': ('id', 'task', 'author')
        }),
        ('Содержание', {
            'fields': ('content', 'is_edited')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(TaskHistory)
class TaskHistoryAdmin(admin.ModelAdmin):
    list_display = ['task', 'field_name', 'changed_by', 'changed_at']
    list_filter = ['field_name', 'changed_at']
    search_fields = ['task__title', 'changed_by__username']
    readonly_fields = ['id', 'task', 'changed_by', 'field_name', 'old_value', 'new_value', 'changed_at']
    fieldsets = (
        ('Информация об изменении', {
            'fields': ('id', 'task', 'changed_by', 'field_name', 'changed_at')
        }),
        ('Значения', {
            'fields': ('old_value', 'new_value')
        }),
    )

    def has_add_permission(self, request):
        """История создается автоматически, ручное добавление запрещено"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Разрешить каскадное удаление истории при удалении задачи"""
        return True

    def has_change_permission(self, request, obj=None):
        """Запретить редактирование истории"""
        return False
