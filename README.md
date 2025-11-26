# ToDo REST API

Полнофункциональное REST API для системы управления задачами (ToDo) с поддержкой делегирования задач между пользователями.

## Архитектура БД

### Модели

**1. User** (встроенная модель Django)
- Пользователи системы
- Индексы: username, email, is_active

**2. Task** (основная модель)
- Заголовок, описание, статус (pending, in_progress, completed, cancelled)
- Приоритет (low, medium, high, urgent)
- Создатель, дедлайн, даты создания/обновления
- Мягкое удаление (is_deleted с custom manager)
- **Индексы:**
  - status, priority, created_by, created_at, due_date, is_deleted
  - Составные: (status, priority), (created_by, is_deleted)

**3. TaskAssignment** (промежуточная M2M модель)
- Связь Task ↔ User с дополнительными данными
- Роли: owner, assignee, reviewer
- Статус назначения: pending, accepted, rejected
- Информация о том, кто назначил, примечания
- UNIQUE constraint на (task, user)
- **Индексы:**
  - (task, user), (task, status), (user, status), (task, role)

**4. TaskComment** (комментарии к задачам)
- Связь к Task и Author (User)
- Отслеживание редактирования
- **Индексы:**
  - (task, created_at), author

**5. TaskHistory** (лог аудита)
- Отслеживание всех изменений Task
- Поля: field_name, old_value, new_value, changed_at, changed_by
- **Индексы:**
  - (task, field_name), (task, changed_at), changed_by

## Ключевые особенности

### Мягкое удаление (Soft Delete)
- Используется `is_deleted` поле в Task
- Custom manager:
  - `Task.objects` - только активные задачи (для API)
  - `Task.all_objects` - все задачи включая удаленные (для админа)
- Django admin показывает все задачи с фильтром по is_deleted

### Статусные переходы (Гибкая валидация)
Запрещенные переходы:
- completed → in_progress (нельзя, нужно через pending)
- cancelled → in_progress (нужно через pending)

Разрешенные переходы:
- pending → [in_progress, cancelled, pending]
- in_progress → [completed, cancelled, pending]
- completed → [cancelled, pending]
- cancelled → [pending]

### Автоматическое логирование
Django signals автоматически:
1. Создают начальное TaskAssignment (owner) при создании Task
2. Логируют все изменения важных полей в TaskHistory
3. Логируют создание и изменения статуса назначений

### Валидация
- due_date не может быть в прошлом
- Нельзя назначить задачу неактивному пользователю
- Нельзя назначить задачу самому себе
- Проверка уникальности (task, user) в TaskAssignment

## Установка и запуск

### 1. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Применение миграций
```bash
python manage.py migrate
```

### 4. Создание суперпользователя
```bash
python manage.py createsuperuser
```

### 5. Запуск сервера разработки
```bash
python manage.py runserver
```

Приложение будет доступно по адресу: http://localhost:8000/

## Доступ к админ-панели

- **Админ-панель:** http://localhost:8000/admin/
- **API Swagger UI:** http://localhost:8000/api/schema/swagger-ui/
- **API ReDoc:** http://localhost:8000/api/schema/redoc/

## Структура проекта

```
todo_test/
├── config/
│   ├── settings/
│   │   ├── base.py         # Основные настройки
│   │   ├── development.py  # Настройки для разработки (SQLite)
│   │   └── production.py   # Настройки для продакшена (PostgreSQL)
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/               # Основное приложение (URLs routing)
│   ├── tasks/
│   │   ├── models.py       # 4 модели: Task, TaskAssignment, TaskComment, TaskHistory
│   │   ├── managers.py     # Custom manager для soft delete
│   │   ├── signals.py      # Django signals для логирования и валидации
│   │   ├── admin.py        # Django admin конфигурация
│   │   └── urls.py
│   └── users/
│       ├── models.py       # Используем встроенную Django User
│       └── urls.py
├── manage.py
├── requirements.txt
└── README.md
```

## Примеры использования БД

### Создание задачи
```python
from apps.tasks.models import Task
from django.contrib.auth.models import User

user = User.objects.first()
task = Task.objects.create(
    title="Разработать модуль аутентификации",
    description="Реализовать JWT аутентификацию",
    priority="high",
    created_by=user
)
# Автоматически создается TaskAssignment с ролью owner
```

### Назначение задачи
```python
from apps.tasks.models import TaskAssignment

assignment = TaskAssignment.objects.create(
    task=task,
    user=other_user,
    assigned_by=user,
    role="assignee",
    notes="Прошу помочь с этой задачей"
)
# Статус по умолчанию: pending (требует принятия)
```

### Отслеживание истории
```python
# Автоматически логируется при сохранении
task.status = 'in_progress'
task.save()

# История будет доступна здесь
task.history.all()  # Все изменения
task.history.filter(field_name='status')  # Только изменения статуса
```

### Запросы для API
```python
# Только активные задачи
Task.objects.all()  # Использует custom manager

# Все задачи включая удаленные (для админа)
Task.all_objects.all()

# Задачи определенного пользователя
user.created_tasks.all()

# Задачи, назначенные конкретному пользователю
user.task_assignments.filter(status='accepted')

# Только удаленные задачи
Task.objects.deleted()
```

## Индексы производительности

### Основные индексы (High Priority)
- Task: status, priority, created_by, created_at, due_date, is_deleted
- TaskAssignment: (task, user), (task, status), (user, status)
- TaskComment: (task, created_at)
- TaskHistory: (task, field_name), (task, changed_at)

### Составные индексы (Medium Priority)
- Task: (status, priority), (created_by, is_deleted)
- TaskAssignment: (task, role)
- Все улучшения N+1 через select_related() и prefetch_related()

## Миграция на PostgreSQL

Для использования PostgreSQL в production:

1. Обновить `config/settings/base.py`:
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

2. Установить psycopg2:
```bash
pip install psycopg2-binary
```

3. Применить миграции:
```bash
python manage.py migrate
```

## Критерии успеха архитектуры БД

✅ Все связи правильно определены (ForeignKey, ManyToMany через промежуточную модель)
✅ UNIQUE ограничения предотвращают дублирующиеся назначения
✅ Индексы оптимизируют частые паттерны запросов
✅ Soft delete реализован с custom manager для разных представлений
✅ TaskAssignment правильно моделирует M2M с дополнительными данными
✅ Отслеживание истории через signals
✅ Валидация статусных переходов
✅ Нет N+1 проблем благодаря структуре моделей

## Следующие шаги

1. **REST API Views & Serializers** - Создать сериализаторы и viewsets для всех моделей
2. **Authentication & Permissions** - JWT аутентификация и custom permissions
3. **Filtering & Pagination** - Реализовать фильтрацию, поиск, сортировку
4. **Testing** - Написать unit и integration тесты
5. **API Documentation** - Автоматическая документация через drf-spectacular
