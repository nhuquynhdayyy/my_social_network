# chat/urls.py

from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Danh sách các cuộc hội thoại
    path('', views.conversation_list_view, name='conversation_list'),

    # Bắt đầu một cuộc hội thoại mới với một người dùng
    path('start/<int:user_id>/', views.start_conversation_view, name='start_conversation'),

    # Chi tiết một cuộc hội thoại (phòng chat)
    path('<int:conversation_id>/', views.conversation_detail_view, name='conversation_detail'),
    
    # path('chat/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),

    # API nội bộ để gửi tin nhắn (sử dụng với JavaScript)
    path('api/message/send/<int:conversation_id>/', views.send_message_api, name='send_message_api'),

    # API nội bộ để xóa tin nhắn
    path('api/message/delete/<int:message_id>/', views.delete_message_api, name='delete_message_api'),
    
    # API nội bộ để sửa tin nhắn
    path('api/message/edit/<int:message_id>/', views.edit_message_api, name='edit_message_api'),
    path('api/conversations/', views.api_get_conversations, name='api_get_conversations'),
    path('api/search-users/', views.api_search_users, name='api_search_users'),
    path('api/message/react/<int:message_id>/', views.react_to_message_api, name='react_to_message_api'),
    path('api/conversation/<int:conversation_id>/messages/', views.api_get_messages, name='api_get_messages'),
]