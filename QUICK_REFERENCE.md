# Быстрый справочник по архитектуре БД ToDo API

## Структура в одном взгляде

```
┌────────────────────────────────────────────────────────────────┐
│                         МОДЕЛИ                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  User (Django встроенная)                                     │
│  ├─ id, username, email, password, is_active                 │
│                                                                │
│  Task (UUID)                                                   │
│  ├─ title, description, status, priority                      │
│  ├─ created_by (FK→User), due_date                           │
│  ├─ created_at, updated_at, is_deleted (soft delete)         │
│  ├─ Индексы: status, priority, created_by, created_at       │
│  ├─ Custom manager: objects (active), all_objects (all)      │
│                                                                │
│  TaskAssignment (UUID) - M2M через промежуточную модель      │
│  ├─ task (FK→Task), user (FK→User)                           │
│  ├─ assigned_by (FK→User), role, status                      │
│  ├─ assigned_at, notes                                        │
│  ├─ UNIQUE(task, user), CHECK(user != assigned_by)           │
│                                                                │
│  TaskComment (UUID)                                            │
│  ├─ task (FK→Task), author (FK→User)                         │
│  ├─ content, is_edited, created_at, updated_at               │
│                                                                │
│  TaskHistory (UUID) - Аудит-лог                               │
│  ├─ task (FK→Task), changed_by (FK→User)                     │
│  ├─ field_name, old_value, new_value, changed_at             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Основные команды Django

```bash
# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Просмотр SQL миграции
python manage.py sqlmigrate tasks 0001

# Создание суперпользователя
python manage.py createsuperuser

# Django shell
python manage.py shell

# Запуск сервера
python manage.py runserver

# Запуск тестов
python manage.py test apps.tasks

# Создание дампа данных
python manage.py dumpdata > dump.json

# Загрузка из дампа
python manage.py loaddata dump.json
```

## Django ORM Хитрости

### Создание
```python
# Создать объект
task = Task.objects.create(
    title='Название',
    created_by=user
)

# Получить или создать
task, created = Task.objects.get_or_create(
    id=uuid,
    defaults={'title': 'Название'}
)
```

### Фильтрация
```python
# Только активные (автоматически через custom manager)
tasks = Task.objects.all()

# Все включая удаленные
all_tasks = Task.all_objects.all()

# Только удаленные
deleted_tasks = Task.objects.deleted()

# Фильтрация
tasks = Task.objects.filter(status='pending', priority='high')

# Исключение
tasks = Task.objects.exclude(status='cancelled')

# Q-объекты (OR)
from django.db.models import Q
tasks = Task.objects.filter(
    Q(status='pending') | Q(status='in_progress')
)
```

### Получение одного объекта
```python
# По ID
task = Task.objects.get(id=task_id)

# По условию
task = Task.objects.get(title='Название')

# Первый
task = Task.objects.first()

# Последний
task = Task.objects.last()
```

### Сортировка
```python
# По возрастанию
tasks = Task.objects.order_by('created_at')

# По убыванию
tasks = Task.objects.order_by('-created_at')

# Несколько полей
tasks = Task.objects.order_by('-priority', 'due_date')
```

### Агрегация и аннотация
```python
from django.db.models import Count, Sum, Avg, Max, Min

# Count
tasks_count = Task.objects.count()

# Аннотация (добавить поле)
tasks = Task.objects.annotate(
    comment_count=Count('comments')
)

# Условное добавление
from django.db.models import Case, When
tasks = Task.objects.annotate(
    is_completed=Case(
        When(status='completed', then=True),
        default=False
    )
)

# Фильтрация после аннотации
high_activity = Task.objects.annotate(
    comment_count=Count('comments')
).filter(comment_count__gt=5)
```

### Оптимизация запросов
```python
# Select related (для ForeignKey)
tasks = Task.objects.select_related('created_by')

# Prefetch related (для обратных FK и M2M)
tasks = Task.objects.prefetch_related('assignments', 'comments')

# Комбинация
tasks = Task.objects.select_related(
    'created_by'
).prefetch_related(
    'assignments', 'comments'
)

# Кастомный prefetch
from django.db.models import Prefetch
tasks = Task.objects.prefetch_related(
    Prefetch(
        'assignments',
        queryset=TaskAssignment.objects.filter(status='accepted')
    )
)
```

### Update/Delete
```python
# Batch update
Task.objects.filter(status='pending').update(status='in_progress')

# Batch delete
Task.objects.filter(is_deleted=True).delete()

# Soft delete
task = Task.objects.get(id=task_id)
task.soft_delete()
```

## Статусные переходы

```
┌─────────────┐
│   pending   │
├─────────────┤
│ в: in_progress, cancelled, pending
│ из: (любой)
└─────────────┘
     ↓
┌──────────────────┐
│   in_progress    │
├──────────────────┤
│ в: completed, cancelled, pending
│ из: pending
└──────────────────┘
     ↓
┌─────────────┐
│ completed   │ ❌ ФИНАЛЬНЫЙ (можно в pending или cancelled)
├─────────────┤
│ в: cancelled, pending (restart)
│ из: in_progress
└─────────────┘
     ↑
┌─────────────┐
│ cancelled   │
├─────────────┤
│ в: pending (resume)
│ из: любой
└─────────────┘
```

## Индексы для проверки

| Таблица | Индекс | Тип | Назначение |
|---------|--------|-----|-----------|
| task | status | single | Фильтр по статусу |
| task | priority | single | Сортировка, фильтр |
| task | created_by | single | Мои задачи |
| task | created_at | single | Сортировка |
| task | due_date | single | Deadline queries |
| task | is_deleted | single | Soft delete |
| task | (status, priority) | composite | Частые комбинации |
| task | (created_by, is_deleted) | composite | Мои активные |
| task_assignment | (task, user) | UNIQUE | Предотвращение дубликатов |
| task_assignment | (task, status) | composite | Получить accepted |
| task_assignment | (user, status) | composite | Мне назначенные |
| task_comment | (task, created_at) | composite | Сортировка комментариев |
| task_history | (task, field_name) | composite | История поля |

## Constraints

| Таблица | Constraint | Тип | Проверка |
|---------|-----------|-----|----------|
| task_assignment | UNIQUE(task, user) | Unique | Нельзя назначить дважды |
| task_assignment | user != assigned_by | Check | Нельзя самому себе |
| task | due_date > created_at | Валидация | Дедлайн в будущем |
| task | status переходы | Валидация | Правильные переходы |

## Сигналы Django

```python
# Автоматические действия

# 1. Когда создается Task:
#    - post_save создает TaskAssignment (creator as owner)

# 2. Когда обновляется Task:
#    - pre_save валидирует переход статусов
#    - post_save создает записи в TaskHistory

# 3. Когда изменяется TaskAssignment:
#    - post_save создает запись в TaskHistory
```

## API Endpoints (будут реализованы)

```
GET    /api/tasks/               - Список задач
POST   /api/tasks/               - Создать
GET    /api/tasks/{id}/          - Детали
PUT    /api/tasks/{id}/          - Обновить полностью
PATCH  /api/tasks/{id}/          - Обновить частично
DELETE /api/tasks/{id}/          - Удалить (soft)

GET    /api/tasks/my/            - Мои созданные
GET    /api/tasks/assigned/      - Мне назначенные
GET    /api/tasks/{id}/history/  - История изменений

POST   /api/tasks/{id}/assign/   - Назначить
DELETE /api/tasks/{id}/unassign/ - Снять назначение
GET    /api/tasks/{id}/assignees/ - Список назначенных

GET    /api/tasks/{id}/comments/ - Комментарии
POST   /api/tasks/{id}/comments/ - Добавить комментарий
```

## Файлы проекта

| Файл | Строк | Назначение |
|------|-------|-----------|
| models.py | 310 | 4 модели + валидация |
| managers.py | 24 | Custom manager для soft delete |
| signals.py | 85 | Автоматическое логирование |
| admin.py | 95 | Django admin конфиг |
| settings/base.py | 227 | Основные настройки |
| settings/development.py | 14 | SQLite для разработки |
| settings/production.py | 25 | PostgreSQL для продакшена |

## Миграция на PostgreSQL

```bash
# 1. Установить драйвер
pip install psycopg2-binary

# 2. Создать БД
createdb todo_db

# 3. Обновить settings
# В DATABASES -> default -> ENGINE и параметры

# 4. Применить миграции
python manage.py migrate

# 5. Создать индексы (дополнительно)
# Из SQL_EXAMPLES.md
```

## Резервное копирование

```bash
# SQLite
cp db.sqlite3 db.sqlite3.backup

# PostgreSQL
pg_dump todo_db > backup.sql
pg_dump -Fc todo_db > backup.dump

# Restore
psql todo_db < backup.sql
pg_restore -d todo_db backup.dump
```

## Решение типичных проблем

| Проблема | Решение |
|----------|---------|
| "No changes detected" при makemigrations | `python manage.py makemigrations apps.tasks` |
| IntegrityError при создании | Проверить constraints (UNIQUE, CHECK) |
| N+1 queries | Добавить select_related() и prefetch_related() |
| Задача видима в queries после soft_delete | Использовать Task.all_objects вместо Task.objects |
| Сигналы не срабатывают | Проверить apps.py ready() метод |
| Тесты не видят модели | Запустить `python manage.py test` вместо pytest |

## Типичные запросы

```python
# Задачи пользователя с информацией
user.created_tasks.all()

# Мне назначенные
user.task_assignments.filter(status='accepted')

# Задачи в процессе
Task.objects.filter(status='in_progress')

# Задачи без дедлайна
Task.objects.filter(due_date__isnull=True)

# Задачи с дедлайном в течение недели
from django.utils import timezone
from datetime import timedelta
Task.objects.filter(
    due_date__lte=timezone.now() + timedelta(days=7),
    status__in=['pending', 'in_progress']
)

# Задачи с комментариями
Task.objects.annotate(
    comment_count=Count('comments')
).filter(comment_count__gt=0)

# История изменений
task.history.filter(field_name='status').order_by('-changed_at')

# Кто назначен на задачу
task.assignments.all().values_list('user__username', flat=True)
```

## Производство

```python
# settings/production.py должен быть настроен

DEBUG = False  # ВАЖНО!
ALLOWED_HOSTS = ['yourdomain.com']  # ВАЖНО!
SECRET_KEY = os.environ.get('SECRET_KEY')  # ВАЖНО!

# Запуск с Gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000

# Запуск с uWSGI
uwsgi --http :8000 --wsgi-file config/wsgi.py --callable application
```

## Документация

- 📖 **README.md** - Быстрый старт
- 📋 **DATABASE_ARCHITECTURE.md** - Подробная архитектура
- ✅ **IMPLEMENTATION_SUMMARY.md** - Что сделано
- 🧪 **TESTING_GUIDE.md** - Как тестировать
- 📝 **SQL_EXAMPLES.md** - SQL примеры
- 📌 **QUICK_REFERENCE.md** - Этот файл
