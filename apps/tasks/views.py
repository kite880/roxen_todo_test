from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.contrib.auth.models import User
from .models import Task, TaskAssignment, TaskComment, TaskHistory
from .serializers import (
    TaskListSerializer, TaskDetailSerializer, TaskCreateUpdateSerializer,
    TaskAssignmentSerializer, TaskCommentSerializer, TaskHistorySerializer
)


class TaskViewSet(viewsets.ModelViewSet):
    """ViewSet для управления задачами"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'created_by']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority']
    ordering = ['-created_at']
    tags = ['Tasks']

    def get_queryset(self):
        """Получить только задачи, видимые текущему пользователю"""
        user = self.request.user
        # Показать свои задачи и задачи, на которые назначен
        return Task.objects.filter(
            Q(created_by=user) |
            Q(assignments__user=user)
        ).distinct().select_related('created_by').prefetch_related(
            'assignments', 'comments', 'history'
        )

    def get_serializer_class(self):
        """Выбрать сериализатор в зависимости от action"""
        if self.action == 'retrieve':
            return TaskDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TaskCreateUpdateSerializer
        return TaskListSerializer

    @action(detail=False, methods=['get'], tags=['Tasks - My Tasks'])
    def my_tasks(self, request):
        """Получить мои созданные задачи"""
        tasks = Task.objects.filter(created_by=request.user).select_related('created_by')
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], tags=['Tasks - My Tasks'])
    def assigned_to_me(self, request):
        """Получить задачи, назначенные мне"""
        tasks = Task.objects.filter(
            assignments__user=request.user,
            assignments__status='accepted'
        ).select_related('created_by').distinct()
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], tags=['Tasks - Assignment'])
    def assign(self, request, pk=None):
        """Назначить задачу пользователю"""
        task = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', 'assignee')
        notes = request.data.get('notes', '')

        if not user_id:
            return Response({'error': 'user_id обязателен'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь не найден'}, status=status.HTTP_404_NOT_FOUND)

        assignment, created = TaskAssignment.objects.get_or_create(
            task=task,
            user=user,
            defaults={
                'assigned_by': request.user,
                'role': role,
                'notes': notes
            }
        )

        if not created:
            return Response(
                {'error': 'Пользователь уже назначен на эту задачу'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TaskAssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], tags=['Tasks - Assignment'])
    def unassign(self, request, pk=None):
        """Снять назначение с пользователя"""
        task = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response({'error': 'user_id обязателен'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            assignment = TaskAssignment.objects.get(task=task, user_id=user_id)
            assignment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TaskAssignment.DoesNotExist:
            return Response({'error': 'Назначение не найдено'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'], tags=['Tasks - History'])
    def history(self, request, pk=None):
        """Получить историю изменений задачи"""
        task = self.get_object()
        history = task.history.all().order_by('-changed_at')
        serializer = TaskHistorySerializer(history, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], tags=['Tasks - Management'])
    def restore(self, request, pk=None):
        """Восстановить удаленную задачу"""
        try:
            task = Task.all_objects.get(id=pk)
            if not task.is_deleted:
                return Response(
                    {'error': 'Задача не удалена'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            task.restore()
            serializer = self.get_serializer(task)
            return Response(serializer.data)
        except Task.DoesNotExist:
            return Response({'error': 'Задача не найдена'}, status=status.HTTP_404_NOT_FOUND)


class TaskCommentViewSet(viewsets.ModelViewSet):
    """ViewSet для комментариев к задачам"""
    permission_classes = [IsAuthenticated]
    serializer_class = TaskCommentSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['task']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    tags = ['Comments']

    def get_queryset(self):
        """Получить комментарии видимых задач"""
        user = self.request.user
        return TaskComment.objects.filter(
            Q(task__created_by=user) |
            Q(task__assignments__user=user)
        ).distinct()

    def perform_create(self, serializer):
        """Автоматически установить автора в текущего пользователя"""
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['get'], tags=['Comments - By Task'])
    def task_comments(self, request, pk=None):
        """Получить все комментарии к задаче"""
        try:
            task = Task.objects.get(id=pk)
            comments = task.comments.all()
            serializer = self.get_serializer(comments, many=True)
            return Response(serializer.data)
        except Task.DoesNotExist:
            return Response({'error': 'Задача не найдена'}, status=status.HTTP_404_NOT_FOUND)


class TaskAssignmentViewSet(viewsets.ModelViewSet):
    """ViewSet для назначений задач"""
    permission_classes = [IsAuthenticated]
    serializer_class = TaskAssignmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task', 'user', 'status', 'role']
    tags = ['Assignments']

    def get_queryset(self):
        """Получить только назначения видимых задач"""
        user = self.request.user
        return TaskAssignment.objects.filter(
            Q(task__created_by=user) |
            Q(task__assignments__user=user)
        ).distinct()

    @action(detail=True, methods=['patch'], tags=['Assignments - Status'])
    def accept(self, request, pk=None):
        """Принять назначение"""
        assignment = self.get_object()
        assignment.status = 'accepted'
        assignment.save()
        serializer = self.get_serializer(assignment)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], tags=['Assignments - Status'])
    def reject(self, request, pk=None):
        """Отклонить назначение"""
        assignment = self.get_object()
        assignment.status = 'rejected'
        assignment.save()
        serializer = self.get_serializer(assignment)
        return Response(serializer.data)
