from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list_view, name='notification_list'),
    path('api/', views.get_notifications, name='get_notifications'),
    path('redirect/<int:pk>/', views.redirect_notification, name='redirect'),
    path('mark-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),
    path('mark-unread/<int:notification_id>/', views.mark_as_unread, name='mark_as_unread'),
]