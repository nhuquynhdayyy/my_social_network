from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('api/', views.get_notifications, name='get_notifications'),
    path('redirect/<int:pk>/', views.redirect_notification, name='redirect'),
]