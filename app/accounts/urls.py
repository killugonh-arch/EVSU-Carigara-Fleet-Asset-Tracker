from django.urls import path
from . import views

urlpatterns = [
    path('login/',    views.login_view,      name='login'),
    path('logout/',   views.logout_view,     name='logout'),
    path('register/', views.register_view,   name='register'),
    path('users/',    views.user_management, name='user_management'),
    path('users/<int:pk>/delete/', views.delete_user, name='delete_user'),
]