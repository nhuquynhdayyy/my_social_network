# chat/urls.py

from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list_view, name='conversation_list'),
    path('new-group/', views.create_group_view, name='create_group'),
    
    # --- THÊM DÒNG NÀY ---
    # URL cho trang quản lý nhóm
    path('<int:conversation_id>/manage/', views.manage_group_view, name='manage_group'),
    path('<int:conversation_id>/leave/', views.leave_group_view, name='leave_group'),
    path('start/<int:user_id>/', views.start_conversation_view, name='start_conversation'),
    path('<int:conversation_id>/', views.conversation_detail_view, name='conversation_detail'),
    
    # Các URL cho API giữ nguyên
    path('api/message/send/<int:conversation_id>/', views.send_message_api, name='send_message_api'),
    path('api/message/delete/<int:message_id>/', views.delete_message_api, name='delete_message_api'),
    path('api/message/edit/<int:message_id>/', views.edit_message_api, name='edit_message_api'),
    path('api/conversations/', views.api_get_conversations, name='api_get_conversations'),
    path('api/search-users/', views.api_search_users, name='api_search_users'),
    path('api/message/react/<int:message_id>/', views.react_to_message_api, name='react_to_message_api'),
    path('api/conversation/<int:conversation_id>/messages/', views.api_get_messages, name='api_get_messages'),
]