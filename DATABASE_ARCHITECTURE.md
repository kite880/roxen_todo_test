# Архитектура базы данных ToDo REST API


## Диаграмма связей

```
┌─────────────┐
│    User     │ (встроенная Django модель)
│ (id: int)   │
└──────┬──────┘
       │
       ├─→ Task.created_by (1:N)
       ├─→ TaskAssignment.user (1:N)
       ├─→ TaskAssignment.assigned_by (1:N)
       ├─→ TaskComment.author (1:N)
       └─→ TaskHistory.changed_by (1:N)

┌─────────────────────────────┐
│         Task                 │ (UUID PK)
├─────────────────────────────┤
│ id: UUID (PK)               │
│ title: CharField(255)       │
│ description: TextField      │
│ status: CharField           │
│ priority: CharField         │
│ created_by: FK→User         │
│ due_date: DateTimeField     │
│ created_at: DateTimeField   │ [indexed]
│ updated_at: DateTimeField   │
│ is_deleted: BooleanField    │ [indexed]
└──────┬──────────────────────┘
       │
       ├─→ TaskAssignment.task (1:N, CASCADE)
       ├─→ TaskComment.task (1:N, CASCADE)
       └─→ TaskHistory.task (1:N, CASCADE)

┌──────────────────────────────┐
│   TaskAssignment             │ (UUID PK)
│ (Промежуточная M2M модель)   │
├──────────────────────────────┤
│ id: UUID (PK)                │
│ task: FK→Task (CASCADE)      │
│ user: FK→User (CASCADE)      │
│ assigned_by: FK→User (PROTECT)│
│ role: CharField              │
│ status: CharField            │
│ assigned_at: DateTimeField   │
│ updated_at: DateTimeField    │
│ notes: TextField             │
│                               │
│ Constraints:                 │
│ - UNIQUE(task, user)         │
│ - CHECK(user != assigned_by) │
└──────────────────────────────┘

┌──────────────────────────────┐
│   TaskComment                │ (UUID PK)
├──────────────────────────────┤
│ id: UUID (PK)                │
│ task: FK→Task (CASCADE)      │
│ author: FK→User (PROTECT)    │
│ content: TextField           │
│ is_edited: BooleanField      │
│ created_at: DateTimeField    │
│ updated_at: DateTimeField    │
└──────────────────────────────┘

┌──────────────────────────────┐
│   TaskHistory                │ (UUID PK)
│ (Лог аудита)                 │
├──────────────────────────────┤
│ id: UUID (PK)                │
│ task: FK→Task (CASCADE)      │
│ changed_by: FK→User (PROTECT)│
│ field_name: CharField        │
│ old_value: TextField         │
│ new_value: TextField         │
│ changed_at: DateTimeField    │
└──────────────────────────────┘
```

## Детальное описание моделей

### 1. Task

**Назначение**: Основная модель для хранения информации о задачах.

**Поля**:
| Поле | Тип | Ограничения | Примечание |
|------|-----|-------------|-----------|
| id | UUID | PK | Уникальный идентификатор |
| title | CharField(255) | NOT NULL | Заголовок задачи |
| description | TextField | NULL | Подробное описание |
| status | CharField | choices | pending, in_progress, completed, cancelled |
| priority | CharField | choices | low, medium, high, urgent |
| created_by | FK(User) | NOT NULL | Создатель задачи |
| due_date | DateTimeField | NULL | Дедлайн |
| created_at | DateTimeField | auto | Дата создания |
| updated_at | DateTimeField | auto | Дата последнего обновления |
| is_deleted | BooleanField | default=False | Флаг мягкого удаления |

**Индексы**:
```sql
-- Single column
CREATE INDEX tasks_task_status ON tasks_task(status);
CREATE INDEX tasks_task_priority ON tasks_task(priority);
CREATE INDEX tasks_task_created_by ON tasks_task(created_by_id);
CREATE INDEX tasks_task_created_at ON tasks_task(created_at);
CREATE INDEX tasks_task_due_date ON tasks_task(due_date);
CREATE INDEX tasks_task_is_deleted ON tasks_task(is_deleted);

-- Composite
CREATE INDEX tasks_task_status_priority ON tasks_task(status, priority);
CREATE INDEX tasks_task_created_by_deleted ON tasks_task(created_by_id, is_deleted);

-- Partial (PostgreSQL)
CREATE INDEX tasks_task_active ON tasks_task(id) WHERE is_deleted = FALSE;
```

**Валидация**:
- `due_date >= created_at`
- Статус должен следовать определенным переходам
- Нельзя устанавливать дедлайн в прошлом

**Связи**:
- 1:N с TaskAssignment (удаляет все назначения при удалении)
- 1:N с TaskComment (удаляет все комментарии)
- 1:N с TaskHistory (удаляет всю историю)

### 2. TaskAssignment

**Назначение**: Промежуточная модель для M2M связи Task и User с дополнительными данными о назначении.

**Поля**:
| Поле | Тип | Ограничения | Примечание |
|------|-----|-------------|-----------|
| id | UUID | PK | Уникальный идентификатор |
| task | FK(Task) | CASCADE | Ссылка на задачу |
| user | FK(User) | CASCADE | Ссылка на назначенного пользователя |
| assigned_by | FK(User) | PROTECT | Кто сделал назначение |
| role | CharField | choices | owner, assignee, reviewer |
| status | CharField | choices | pending, accepted, rejected |
| assigned_at | DateTimeField | auto | Когда назначена |
| updated_at | DateTimeField | auto | Когда обновлена |
| notes | TextField | NULL | Примечания при назначении |

**Уникальные ограничения**:
```sql
ALTER TABLE tasks_taskassignment
ADD CONSTRAINT unique_task_user UNIQUE(task_id, user_id);

ALTER TABLE tasks_taskassignment
ADD CONSTRAINT check_user_not_assigned_by
CHECK(user_id != assigned_by_id);
```

**Индексы**:
```sql
-- Уникальный (также является индексом для быстрого поиска)
CREATE UNIQUE INDEX tasks_taskassignment_task_user
ON tasks_taskassignment(task_id, user_id);

-- Для поиска назначений по пользователю
CREATE INDEX tasks_taskassignment_user_status
ON tasks_taskassignment(user_id, status);

-- Для получения всех назначенных на задачу
CREATE INDEX tasks_taskassignment_task_status
ON tasks_taskassignment(task_id, status);

-- Для поиска по ролям
CREATE INDEX tasks_taskassignment_task_role
ON tasks_taskassignment(task_id, role);
```

**Поток данных**:
1. Создатель Task → автоматически создается TaskAssignment с role='owner', status='accepted'
2. Владелец назначает task → создается TaskAssignment с role='assignee', status='pending'
3. Пользователь принимает/отклоняет → обновляется status ('accepted' или 'rejected')

### 3. TaskComment

**Назначение**: Хранение комментариев к задачам для сотрудничества.

**Поля**:
| Поле | Тип | Ограничения | Примечание |
|------|-----|-------------|-----------|
| id | UUID | PK | Уникальный идентификатор |
| task | FK(Task) | CASCADE | Ссылка на задачу |
| author | FK(User) | PROTECT | Автор комментария |
| content | TextField | NOT NULL | Содержание комментария |
| is_edited | BooleanField | default=False | Был ли отредактирован |
| created_at | DateTimeField | auto | Дата создания |
| updated_at | DateTimeField | auto | Дата обновления |

**Индексы**:
```sql
CREATE INDEX tasks_taskcomment_task_created
ON tasks_taskcomment(task_id, created_at);

CREATE INDEX tasks_taskcomment_author
ON tasks_taskcomment(author_id);
```

### 4. TaskHistory

**Назначение**: Аудит-лог для отслеживания всех изменений в Task.

**Поля**:
| Поле | Тип | Ограничения | Примечание |
|------|-----|-------------|-----------|
| id | UUID | PK | Уникальный идентификатор |
| task | FK(Task) | CASCADE | Ссылка на задачу |
| changed_by | FK(User) | PROTECT | Кто сделал изменение |
| field_name | CharField | choices | title, description, status, priority, due_date, assignment |
| old_value | TextField | NULL | Старое значение |
| new_value | TextField | NULL | Новое значение |
| changed_at | DateTimeField | auto | Когда произошло изменение |

**Отслеживаемые поля**:
- title, description: текстовые изменения
- status, priority: статус и приоритет
- due_date: изменения дедлайна
- assignment: создание/изменение назначений

**Индексы**:
```sql
CREATE INDEX tasks_taskhistory_task_field
ON tasks_taskhistory(task_id, field_name);

CREATE INDEX tasks_taskhistory_task_changed
ON tasks_taskhistory(task_id, changed_at);

CREATE INDEX tasks_taskhistory_changed_by
ON tasks_taskhistory(changed_by_id);
```

## Реализованные паттерны

### 1. Soft Delete (Мягкое удаление)

**Реализация**:
```python
class TaskManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_objects(self):
        return TaskQuerySet(self.model, using=self._db)

class Task(models.Model):
    objects = TaskManager()  # Только активные
    all_objects = models.Manager()  # Все + удаленные
```

**Преимущества**:
- Восстановление удаленных задач
- Сохранение истории
- Обратная совместимость (стандартные queries видят только активные)

### 2. M2M через промежуточную модель

**Причина**: TaskAssignment нужна для хранения дополнительных данных (role, status, notes, assigned_by).

**Запросы**:
```python
# Получить всех пользователей, назначенных на задачу
task.assignments.all()

# Получить все задачи, назначенные пользователю
user.task_assignments.all()

# Получить задачи с ролью owner
Task.objects.filter(assignments__role='owner')
```

### 3. Django Signals для автоматизации

**post_save на Task**:
1. При создании → автоматически создается TaskAssignment (creator as owner)
2. При обновлении → логируется в TaskHistory

**post_save на TaskAssignment**:
- Логируется в TaskHistory при создании/изменении статуса

### 4. State Machine для статусов

**Разрешенные переходы**:
```
pending ──→ in_progress
  ↓           ↓
cancelled  completed
  ↑           ↓
  └─── pending (restart)
```

**Запрещенные**:
- completed → in_progress (нужно через pending)
- cancelled → in_progress (нужно через pending)

## Оптимизация запросов

### Select Related (Foreign Keys)
```python
# Плохо: N+1 query
tasks = Task.objects.all()
for task in tasks:
    print(task.created_by.username)  # N дополнительных queries

# Хорошо: 2 query
tasks = Task.objects.select_related('created_by')
for task in tasks:
    print(task.created_by.username)  # Из cache
```

### Prefetch Related (Reverse ForeignKey и M2M)
```python
# Плохо: N+1 query
tasks = Task.objects.all()
for task in tasks:
    count = task.assignments.count()  # N дополнительных queries

# Хорошо: 2 query с prefetch
from django.db.models import Prefetch

tasks = Task.objects.prefetch_related('assignments')
for task in tasks:
    count = len(task.assignments.all())  # Из prefetch cache
```

## Миграция на PostgreSQL

### 1. Подготовка
```bash
# Установить psycopg2
pip install psycopg2-binary

# Создать БД
createdb todo_db
```

### 2. Обновить settings
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'todo_db',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 3. Применить миграции
```bash
python manage.py migrate
```

### 4. Дополнительные индексы для PostgreSQL
```sql
-- Partial index для активных задач
CREATE INDEX tasks_task_active_idx
ON tasks_task(id) WHERE is_deleted = FALSE;

-- GiST index для полнотекстового поиска (future)
CREATE INDEX tasks_task_search_idx
ON tasks_task USING GiST(to_tsvector('russian', title || ' ' || description));

-- B-tree индексы для сортировки
CREATE INDEX tasks_task_status_priority_idx
ON tasks_task(status, priority DESC);
```

## Производительность

### Сложные запросы

**Получить активные задачи пользователя с информацией о назначениях**:
```python
from django.db.models import Prefetch

tasks = Task.objects.select_related('created_by').prefetch_related(
    Prefetch('assignments', queryset=TaskAssignment.objects.filter(status='accepted'))
)
```

**Получить задачи с количеством комментариев и активными назначениями**:
```python
from django.db.models import Count, F, Q

tasks = Task.objects.annotate(
    comment_count=Count('comments'),
    active_assignments=Count('assignments', filter=Q(assignments__status='accepted'))
).filter(comment_count__gt=0)
```

## Безопасность

### Защита от SQL injection
- Django ORM автоматически параметризирует запросы
- Используется raw() только для специальных случаев

### Check constraints
```sql
-- Проверка, что пользователь не может назначить задачу самому себе
ALTER TABLE tasks_taskassignment
ADD CONSTRAINT check_valid_assignment
CHECK(user_id != assigned_by_id);
```

### Foreign Key constraints
```sql
-- PROTECT: нельзя удалить User, если он создатель Task
-- CASCADE: удаление Task удаляет все связанные TaskAssignment, TaskComment, TaskHistory
-- PROTECT: нельзя удалить TaskComment автора
```

## Расширение в будущем

### Possible improvements
1. **Subtasks**: Рекурсивная связь Task.parent
2. **Tags**: M2M с промежуточной моделью для категоризации
3. **Time Tracking**: Отслеживание затраченного времени на задачу
4. **Attachments**: Хранение файлов (M2M с File model)
5. **Notifications**: Таблица для уведомлений о событиях
6. **Team Collaboration**: Команды и группы пользователей

## Проверочный список

✅ UUID для основных моделей (Task, TaskAssignment, TaskComment, TaskHistory)
✅ Soft delete с custom manager
✅ M2M через промежуточную модель с дополнительными данными
✅ Все индексы на месте (single и composite)
✅ Django signals для логирования
✅ Валидация статусных переходов
✅ UNIQUE и CHECK constraints
✅ Правильные on_delete поведения
✅ Оптимизация запросов через select/prefetch_related
✅ Поддержка как SQLite (dev) так и PostgreSQL (prod)
