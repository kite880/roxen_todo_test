# Примеры SQL запросов для ToDo API БД

## Основные SELECT запросы

### 1. Получить все активные задачи пользователя (creator)

```sql
SELECT
    t.id,
    t.title,
    t.status,
    t.priority,
    t.created_at,
    t.due_date
FROM tasks_task t
WHERE
    t.created_by_id = <user_id>
    AND t.is_deleted = FALSE
ORDER BY t.created_at DESC;
```

**Django ORM эквивалент**:
```python
Task.objects.filter(
    created_by_id=user_id
).order_by('-created_at')
```

---

### 2. Получить все задачи, назначенные конкретному пользователю

```sql
SELECT
    t.id,
    t.title,
    t.status,
    t.priority,
    ta.role,
    ta.status as assignment_status,
    ta.assigned_at
FROM tasks_task t
JOIN tasks_taskassignment ta ON t.id = ta.task_id
WHERE
    ta.user_id = <user_id>
    AND t.is_deleted = FALSE
    AND ta.status = 'accepted'
ORDER BY t.due_date NULLS LAST;
```

**Django ORM эквивалент**:
```python
Task.objects.filter(
    assignments__user_id=user_id,
    assignments__status='accepted'
).select_related('created_by').prefetch_related('assignments')
```

---

### 3. Получить задачи с количеством комментариев и участников

```sql
SELECT
    t.id,
    t.title,
    t.status,
    COUNT(DISTINCT tc.id) as comment_count,
    COUNT(DISTINCT ta.user_id) as participant_count
FROM tasks_task t
LEFT JOIN tasks_taskcomment tc ON t.id = tc.task_id
LEFT JOIN tasks_taskassignment ta ON t.id = ta.task_id
WHERE t.is_deleted = FALSE
GROUP BY t.id, t.title, t.status
ORDER BY comment_count DESC;
```

**Django ORM эквивалент**:
```python
from django.db.models import Count

Task.objects.annotate(
    comment_count=Count('comments', distinct=True),
    participant_count=Count('assignments__user', distinct=True)
).order_by('-comment_count')
```

---

### 4. Фильтрация задач по статусу и приоритету

```sql
SELECT *
FROM tasks_task
WHERE
    is_deleted = FALSE
    AND status IN ('pending', 'in_progress')
    AND priority IN ('high', 'urgent')
    AND due_date < NOW() + INTERVAL '7 days'
ORDER BY priority DESC, due_date ASC;
```

**Django ORM эквивалент**:
```python
from django.utils import timezone
from datetime import timedelta

Task.objects.filter(
    status__in=['pending', 'in_progress'],
    priority__in=['high', 'urgent'],
    due_date__lt=timezone.now() + timedelta(days=7)
).order_by('-priority', 'due_date')
```

---

### 5. История изменений конкретной задачи

```sql
SELECT
    th.id,
    th.field_name,
    th.old_value,
    th.new_value,
    u.username as changed_by,
    th.changed_at
FROM tasks_taskhistory th
JOIN auth_user u ON th.changed_by_id = u.id
WHERE th.task_id = <task_id>
ORDER BY th.changed_at DESC;
```

**Django ORM эквивалент**:
```python
TaskHistory.objects.filter(
    task_id=task_id
).select_related('changed_by').order_by('-changed_at')
```

---

### 6. Получить задачи с ожидающими назначениями

```sql
SELECT
    t.id,
    t.title,
    u.username as created_by,
    ta.user_id,
    ta.assigned_at,
    ta.notes
FROM tasks_task t
JOIN tasks_taskassignment ta ON t.id = ta.task_id
JOIN auth_user u ON t.created_by_id = u.id
WHERE
    ta.status = 'pending'
    AND t.is_deleted = FALSE
ORDER BY ta.assigned_at ASC;
```

**Django ORM эквивалент**:
```python
Task.objects.filter(
    assignments__status='pending'
).select_related('created_by').prefetch_related(
    'assignments__user'
).order_by('assignments__assigned_at')
```

---

### 7. Статистика по задачам пользователя

```sql
SELECT
    t.created_by_id,
    u.username,
    COUNT(*) as total_tasks,
    COUNT(CASE WHEN t.status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN t.status = 'in_progress' THEN 1 END) as in_progress,
    COUNT(CASE WHEN t.status = 'pending' THEN 1 END) as pending,
    COUNT(CASE WHEN t.status = 'cancelled' THEN 1 END) as cancelled
FROM tasks_task t
JOIN auth_user u ON t.created_by_id = u.id
WHERE t.is_deleted = FALSE
GROUP BY t.created_by_id, u.username
ORDER BY total_tasks DESC;
```

**Django ORM эквивалент**:
```python
from django.db.models import Count, Case, When, IntegerField

User.objects.annotate(
    total_tasks=Count('created_tasks', filter=Q(created_tasks__is_deleted=False)),
    completed=Count(
        Case(When(created_tasks__status='completed', then=1), output_field=IntegerField())
    ),
    in_progress=Count(
        Case(When(created_tasks__status='in_progress', then=1), output_field=IntegerField())
    )
).order_by('-total_tasks')
```

---

## INSERT/UPDATE операции

### 8. Создание новой задачи

```sql
BEGIN TRANSACTION;

-- Создать задачу
INSERT INTO tasks_task (id, title, description, status, priority, created_by_id, due_date, created_at, updated_at, is_deleted)
VALUES (
    gen_random_uuid(),
    'Разработать модуль аутентификации',
    'Реализовать JWT с refresh токенами',
    'pending',
    'high',
    <user_id>,
    NOW() + INTERVAL '7 days',
    NOW(),
    NOW(),
    FALSE
);

-- Автоматически создается TaskAssignment (creator as owner)
-- Это делается через Django signal

COMMIT;
```

---

### 9. Обновление статуса задачи

```sql
BEGIN TRANSACTION;

-- Обновить статус
UPDATE tasks_task
SET status = 'in_progress', updated_at = NOW()
WHERE id = <task_id>;

-- Создать запись в истории (через Django signal)
INSERT INTO tasks_taskhistory (id, task_id, changed_by_id, field_name, old_value, new_value, changed_at)
VALUES (
    gen_random_uuid(),
    <task_id>,
    <user_id>,
    'status',
    'pending',
    'in_progress',
    NOW()
);

COMMIT;
```

**Django эквивалент**:
```python
task = Task.objects.get(id=task_id)
task.status = 'in_progress'
task.save(update_fields=['status'])  # Signal автоматически создаст историю
```

---

### 10. Назначение задачи пользователю

```sql
BEGIN TRANSACTION;

-- Создать назначение
INSERT INTO tasks_taskassignment (id, task_id, user_id, assigned_by_id, role, status, assigned_at, updated_at, notes)
VALUES (
    gen_random_uuid(),
    <task_id>,
    <assignee_user_id>,
    <assigner_user_id>,
    'assignee',
    'pending',
    NOW(),
    NOW(),
    'Требуется ваше участие в этой задаче'
);

-- Создается запись в истории через signal

COMMIT;
```

**Django эквивалент**:
```python
TaskAssignment.objects.create(
    task_id=task_id,
    user_id=assignee_user_id,
    assigned_by_id=assigner_user_id,
    role='assignee',
    notes='Требуется ваше участие в этой задаче'
)  # Signal автоматически создаст историю
```

---

### 11. Принятие назначения

```sql
BEGIN TRANSACTION;

-- Обновить статус назначения
UPDATE tasks_taskassignment
SET status = 'accepted', updated_at = NOW()
WHERE id = <assignment_id>;

-- Создать запись в истории
INSERT INTO tasks_taskhistory (id, task_id, changed_by_id, field_name, old_value, new_value, changed_at)
VALUES (
    gen_random_uuid(),
    <task_id>,
    <user_id>,
    'assignment',
    'Статус: pending',
    'Статус: accepted',
    NOW()
);

COMMIT;
```

---

### 12. Мягкое удаление задачи

```sql
BEGIN TRANSACTION;

-- Пометить задачу как удаленную
UPDATE tasks_task
SET is_deleted = TRUE, updated_at = NOW()
WHERE id = <task_id>;

-- Если требуется, удалить связанные данные (логически)
-- Но в данной архитектуре они остаются для истории

COMMIT;
```

**Django эквивалент**:
```python
task = Task.objects.get(id=task_id)
task.soft_delete()  # Метод модели
```

---

### 13. Восстановление удаленной задачи

```sql
UPDATE tasks_task
SET is_deleted = FALSE, updated_at = NOW()
WHERE id = <task_id>;
```

**Django эквивалент**:
```python
task = Task.all_objects.get(id=task_id)  # all_objects включает удаленные
task.restore()  # Метод модели
```

---

## DELETE операции

### 14. Полное удаление задачи (без восстановления)

```sql
BEGIN TRANSACTION;

-- Удалить комментарии
DELETE FROM tasks_taskcomment WHERE task_id = <task_id>;

-- Удалить назначения
DELETE FROM tasks_taskassignment WHERE task_id = <task_id>;

-- Удалить историю
DELETE FROM tasks_taskhistory WHERE task_id = <task_id>;

-- Удалить саму задачу
DELETE FROM tasks_task WHERE id = <task_id>;

COMMIT;
```

⚠️ **Внимание**: В продакшене обычно используется мягкое удаление, а не полное.

---

## Оптимизированные запросы

### 15. Получить dashboard для пользователя

```sql
-- Статистика
SELECT
    (SELECT COUNT(*) FROM tasks_task WHERE created_by_id = <user_id> AND is_deleted = FALSE) as my_tasks_count,
    (SELECT COUNT(*) FROM tasks_taskassignment WHERE user_id = <user_id> AND status = 'accepted') as assigned_tasks_count,
    (SELECT COUNT(*) FROM tasks_taskassignment WHERE user_id = <user_id> AND status = 'pending') as pending_assignments_count,
    (SELECT COUNT(*) FROM tasks_task
        WHERE created_by_id = <user_id> AND status = 'completed' AND is_deleted = FALSE) as completed_count;

-- Мои недавние задачи
SELECT * FROM tasks_task
WHERE created_by_id = <user_id> AND is_deleted = FALSE
ORDER BY created_at DESC LIMIT 5;

-- Мне назначенные (ожидают действия)
SELECT * FROM tasks_taskassignment
WHERE user_id = <user_id> AND status = 'pending'
ORDER BY assigned_at DESC LIMIT 5;
```

**Django эквивалент**:
```python
from django.db.models import Count, Q

dashboard = {
    'my_tasks': Task.objects.filter(
        created_by_id=user_id
    ).count(),
    'assigned_tasks': TaskAssignment.objects.filter(
        user_id=user_id,
        status='accepted'
    ).count(),
    'pending_assignments': TaskAssignment.objects.filter(
        user_id=user_id,
        status='pending'
    ).count(),
    'completed_tasks': Task.objects.filter(
        created_by_id=user_id,
        status='completed'
    ).count(),
}

recent_tasks = Task.objects.filter(
    created_by_id=user_id
).order_by('-created_at')[:5]

pending = TaskAssignment.objects.filter(
    user_id=user_id,
    status='pending'
).select_related('task').order_by('-assigned_at')[:5]
```

---

## Индексы для оптимизации

### Проверить использование индексов

```sql
-- PostgreSQL: Analyze index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Использование индексов
EXPLAIN ANALYZE
SELECT * FROM tasks_task
WHERE status = 'in_progress' AND created_by_id = <user_id>;
```

---

## Советы для производительности

1. **Для больших таблиц**: Использовать LIMIT и OFFSET
2. **Для сложных запросов**: Применять select_related() и prefetch_related()
3. **Для поиска**: Использовать full-text search индексы
4. **Для временных рядов**: Партиционирование по дате (future)
5. **Кеширование**: Redis для часто используемых запросов

---

## Миграция данных

### Если потребуется миграция из другой системы

```sql
-- Пример импорта из legacy таблицы
INSERT INTO tasks_task (id, title, description, status, priority, created_by_id, due_date, created_at, updated_at, is_deleted)
SELECT
    gen_random_uuid(),
    legacy_task.title,
    legacy_task.description,
    CASE legacy_task.status
        WHEN 1 THEN 'pending'
        WHEN 2 THEN 'in_progress'
        WHEN 3 THEN 'completed'
        ELSE 'cancelled'
    END,
    CASE legacy_task.priority
        WHEN 1 THEN 'low'
        WHEN 2 THEN 'medium'
        WHEN 3 THEN 'high'
        WHEN 4 THEN 'urgent'
    END,
    au.id,  -- JOIN с новой таблицей users
    legacy_task.deadline,
    legacy_task.created_at,
    NOW(),
    FALSE
FROM legacy_tasks legacy_task
JOIN auth_user au ON legacy_task.owner_email = au.email;
```

---

## Резервная копия

### Backup БД PostgreSQL

```bash
# Создать dump
pg_dump todo_db > todo_db_backup.sql

# Restore из dump
psql todo_db < todo_db_backup.sql

# Или с pg_restore
pg_dump -Fc todo_db > todo_db_backup.dump
pg_restore -d todo_db todo_db_backup.dump
```
