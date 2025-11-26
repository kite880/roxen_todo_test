from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, TaskCommentViewSet, TaskAssignmentViewSet

app_name = 'tasks'

# Создаем отдельные routers для каждого типа
tasks_router = DefaultRouter()
tasks_router.register(r'tasks', TaskViewSet, basename='task')

comments_router = DefaultRouter()
comments_router.register(r'comments', TaskCommentViewSet, basename='comment')

assignments_router = DefaultRouter()
assignments_router.register(r'assignments', TaskAssignmentViewSet, basename='assignment')

urlpatterns = [
    path('', include(tasks_router.urls)),
    path('', include(comments_router.urls)),
    path('', include(assignments_router.urls)),
]
