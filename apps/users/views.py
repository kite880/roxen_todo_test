from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.models import User
from .serializers import (
    UserSerializer, UserListSerializer, UserCreateUpdateSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet для управления пользователями"""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'date_joined']
    ordering = ['-date_joined']
    tags = ['Users']

    def get_queryset(self):
        """Получить список пользователей"""
        return User.objects.all()

    def get_serializer_class(self):
        """Выбрать сериализатор в зависимости от action"""
        if self.action == 'retrieve':
            return UserSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return UserCreateUpdateSerializer
        return UserListSerializer

    def get_permissions(self):
        """Разрешить создание пользователя без аутентификации, остальное требует аутентификации"""
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], tags=['Users - Profile'])
    def me(self, request):
        """Получить информацию о текущем пользователе"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], tags=['Users - Management'])
    def activate(self, request, pk=None):
        """Активировать пользователя"""
        user = self.get_object()
        user.is_active = True
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], tags=['Users - Management'])
    def deactivate(self, request, pk=None):
        """Деактивировать пользователя"""
        user = self.get_object()
        user.is_active = False
        user.save()
        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], tags=['Users - Management'])
    def change_password(self, request, pk=None):
        """Изменить пароль пользователя"""
        user = self.get_object()
        new_password = request.data.get('password')

        if not new_password:
            return Response(
                {'error': 'password обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()
        return Response({'message': 'Пароль успешно изменен'})

    @action(detail=False, methods=['get'], tags=['Users - Search'])
    def active(self, request):
        """Получить список активных пользователей"""
        users = User.objects.filter(is_active=True)
        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], tags=['Users - Search'])
    def staff(self, request):
        """Получить список сотрудников (staff)"""
        users = User.objects.filter(is_staff=True)
        serializer = self.get_serializer(users, many=True)
        return Response(serializer.data)
