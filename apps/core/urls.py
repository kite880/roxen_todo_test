from django.urls import path, include

urlpatterns = [
    path('auth/', include('apps.users.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('users/', include('apps.users.urls_users')),
]
