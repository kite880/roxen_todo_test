from django.db import models


class TaskQuerySet(models.QuerySet):
    """Custom QuerySet для Task моделей с поддержкой soft delete"""

    def active(self):
        """Вернуть только активные (не удаленные) задачи"""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Вернуть только удаленные задачи"""
        return self.filter(is_deleted=True)


class TaskManager(models.Manager):
    """Custom Manager для Task с поддержкой soft delete"""

    def get_queryset(self):
        """По умолчанию возвращать только активные задачи"""
        return TaskQuerySet(self.model, using=self._db).active()

    def all_objects(self):
        """Вернуть все задачи включая удаленные (для админа)"""
        return TaskQuerySet(self.model, using=self._db)

    def deleted(self):
        """Вернуть только удаленные задачи"""
        return self.get_queryset().deleted()
