import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .managers import TaskManager


class Task(models.Model):
    """Модель основной задачи ToDo"""

    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('in_progress', 'В процессе'),
        ('completed', 'Завершено'),
        ('cancelled', 'Отменено'),
    )

    PRIORITY_CHOICES = (
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, verbose_name='Заголовок')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус',
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name='Приоритет',
        db_index=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_tasks',
        verbose_name='Создана'
    )
    due_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Дедлайн',
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    is_deleted = models.BooleanField(default=False, verbose_name='Удалена', db_index=True)

    # Custom managers
    objects = TaskManager()
    all_objects = models.Manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['created_by', 'is_deleted']),
        ]
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'

    def __str__(self):
        return self.title

    def clean(self):
        """Валидация на уровне модели"""
        super().clean()
        if self.due_date and self.created_at and self.due_date < self.created_at:
            raise ValidationError(
                {'due_date': _('Дедлайн не может быть раньше даты создания')}
            )

    def is_valid_status_transition(self, new_status):
        """Проверка валидности перехода статуса"""
        current_status = self.status

        # Запрещенные переходы
        invalid_transitions = {
            'completed': ['in_progress'],  # из completed нельзя в in_progress
            'cancelled': ['in_progress'],  # из cancelled нельзя напрямую в in_progress
        }

        if current_status in invalid_transitions:
            if new_status in invalid_transitions[current_status]:
                return False

        return True

    def soft_delete(self):
        """Мягкое удаление задачи"""
        self.is_deleted = True
        self.save()

    def restore(self):
        """Восстановление удаленной задачи"""
        self.is_deleted = False
        self.save()


class TaskAssignment(models.Model):
    """Промежуточная модель для M2M связи Task и User с дополнительными данными"""

    ROLE_CHOICES = (
        ('owner', 'Владелец'),
        ('assignee', 'Исполнитель'),
        ('reviewer', 'Рецензент'),
    )

    STATUS_CHOICES = (
        ('pending', 'В ожидании'),
        ('accepted', 'Принято'),
        ('rejected', 'Отклонено'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Задача'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        verbose_name='Пользователь'
    )
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='assignments_made',
        verbose_name='Назначена'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='assignee',
        verbose_name='Роль',
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус',
        db_index=True
    )
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name='Назначена в')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлена в')
    notes = models.TextField(blank=True, null=True, verbose_name='Примечания')

    class Meta:
        unique_together = ('task', 'user')
        indexes = [
            models.Index(fields=['task', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['task', 'role']),
        ]
        verbose_name = 'Назначение задачи'
        verbose_name_plural = 'Назначения задач'

    def __str__(self):
        return f'{self.task.title} -> {self.user.username} ({self.role})'

    def clean(self):
        """Валидация на уровне модели"""
        super().clean()
        # Только валидировать если оба поля установлены
        if self.user and self.assigned_by:
            if self.user == self.assigned_by:
                raise ValidationError(
                    {'user': _('Нельзя назначить задачу самому себе')}
                )
        if self.user and not self.user.is_active:
            raise ValidationError(
                {'user': _('Нельзя назначить задачу неактивному пользователю')}
            )


class TaskComment(models.Model):
    """Модель комментариев к задачам"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name='Задача'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='comments',
        verbose_name='Автор'
    )
    content = models.TextField(verbose_name='Содержание')
    is_edited = models.BooleanField(default=False, verbose_name='Отредактирован')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан в')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен в')

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task', 'created_at']),
            models.Index(fields=['author']),
        ]
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'

    def __str__(self):
        return f'Комментарий от {self.author.username} к {self.task.title}'


class TaskHistory(models.Model):
    """Модель истории изменений задач (лог аудита)"""

    FIELD_CHOICES = (
        ('title', 'Заголовок'),
        ('description', 'Описание'),
        ('status', 'Статус'),
        ('priority', 'Приоритет'),
        ('due_date', 'Дедлайн'),
        ('assignment', 'Назначение'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Задача'
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name='Изменено'
    )
    field_name = models.CharField(
        max_length=100,
        choices=FIELD_CHOICES,
        verbose_name='Измененное поле',
        db_index=True
    )
    old_value = models.TextField(blank=True, null=True, verbose_name='Старое значение')
    new_value = models.TextField(blank=True, null=True, verbose_name='Новое значение')
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата изменения')

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['task', 'field_name']),
            models.Index(fields=['task', 'changed_at']),
            models.Index(fields=['changed_by']),
        ]
        verbose_name = 'История изменений'
        verbose_name_plural = 'История изменений'

    def __str__(self):
        return f'{self.task.title}: {self.field_name} ({self.changed_at})'
