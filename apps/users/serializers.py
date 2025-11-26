from rest_framework import serializers
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для полной информации о пользователе"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка пользователей"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active']
        read_only_fields = ['id']


class UserCreateUpdateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления пользователя"""
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'password', 'is_active']
        read_only_fields = ['id']

    def create(self, validated_data):
        """Создать пользователя с хешированием пароля"""
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        """Обновить пользователя, если указан пароль - хешировать его"""
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate_username(self, value):
        """Проверить что username уникален"""
        if self.instance is None:  # При создании
            if User.objects.filter(username=value).exists():
                raise serializers.ValidationError("Пользователь с таким именем уже существует")
        else:  # При обновлении
            if User.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Пользователь с таким именем уже существует")
        return value
