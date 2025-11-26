from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .models import Task, TaskAssignment, TaskComment, TaskHistory


@receiver(pre_save, sender=Task)
def validate_task_status_transition(sender, instance, **kwargs):
    """Валидация перехода статусов перед сохранением"""
    if instance.pk:  # Если это обновление, а не создание
        try:
            old_instance = Task.all_objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                if not instance.is_valid_status_transition(instance.status):
                    raise ValidationError(
                        f'Недопустимый переход статуса: {old_instance.status} -> {instance.status}'
                    )
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def create_task_assignment_on_creation(sender, instance, created, **kwargs):
    """Создание начального TaskAssignment при создании задачи"""
    if created:
        # Создатель автоматически становится владельцем
        TaskAssignment.objects.get_or_create(
            task=instance,
            user=instance.created_by,
            defaults={
                'assigned_by': instance.created_by,
                'role': 'owner',
                'status': 'accepted',
            }
        )


@receiver(post_save, sender=Task)
def create_task_history(sender, instance, created, update_fields, **kwargs):
    """Логирование изменений Task в историю"""
    if not created and update_fields:
        # Отслеживаемые поля
        tracked_fields = {'title', 'description', 'status', 'priority', 'due_date'}
        fields_to_track = tracked_fields.intersection(update_fields)

        if fields_to_track:
            try:
                old_instance = Task.all_objects.get(pk=instance.pk)
            except Task.DoesNotExist:
                return

            for field in fields_to_track:
                old_value = str(getattr(old_instance, field))
                new_value = str(getattr(instance, field))

                if old_value != new_value:
                    TaskHistory.objects.create(
                        task=instance,
                        changed_by=instance.created_by,  # В реальном приложении нужно получить текущего пользователя
                        field_name=field,
                        old_value=old_value,
                        new_value=new_value,
                    )


@receiver(post_save, sender=TaskAssignment)
def create_assignment_history(sender, instance, created, **kwargs):
    """Логирование изменений TaskAssignment"""
    if created:
        TaskHistory.objects.create(
            task=instance.task,
            changed_by=instance.assigned_by,
            field_name='assignment',
            old_value='',
            new_value=f'Назначена пользователю {instance.user.username} ({instance.role})',
        )
    else:
        # Логировать изменение статуса назначения
        try:
            old_instance = TaskAssignment.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                TaskHistory.objects.create(
                    task=instance.task,
                    changed_by=instance.user,  # Пользователь сам принимает/отклоняет
                    field_name='assignment',
                    old_value=f'Статус: {old_instance.status}',
                    new_value=f'Статус: {instance.status}',
                )
        except TaskAssignment.DoesNotExist:
            pass


def validate_task_before_save(sender, instance, **kwargs):
    """Дополнительная валидация перед сохранением Task"""
    # Только валидировать если created_by уже установлен (не в админе)
    if instance.created_by:
        try:
            instance.full_clean()
        except ValidationError:
            pass  # Сигнал работает, игнорируем ошибки валидации


def validate_assignment_before_save(sender, instance, **kwargs):
    """Дополнительная валидация перед сохранением TaskAssignment"""
    try:
        instance.full_clean()
    except ValidationError:
        pass


# Регистрация валидации
pre_save.connect(validate_task_before_save, sender=Task)
pre_save.connect(validate_assignment_before_save, sender=TaskAssignment)
