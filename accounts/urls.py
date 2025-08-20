# accounts/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    SignUpView, ProfileView, ProfileUpdateView, ProfileDeleteView,
    UserListView, add_friend, FriendRequestListView, accept_friend_request, decline_friend_request
)

# Đặt tên cho app namespace để tránh xung đột
app_name = 'accounts'

urlpatterns = [
    # CÁC URL CỤ THỂ ĐƯỢC ƯU TIÊN ĐẶT LÊN TRÊN CÙNG
    path('register/', SignUpView.as_view(), name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', UserListView.as_view(), name='user_list'),

    # URL cho trang xem danh sách lời mời
    path('requests/', FriendRequestListView.as_view(), name='friend_requests'),
    
    # URL để xử lý chấp nhận
    path('requests/accept/<int:request_id>/', accept_friend_request, name='accept_request'),

    # URL để xử lý từ chối
    path('requests/decline/<int:request_id>/', decline_friend_request, name='decline_request'),
    
    # CÁC URL ĐỘNG PHẢI ĐẶT BÊN DƯỚI
    # Chúng sẽ được kiểm tra sau khi các URL cụ thể ở trên không khớp
    path('add-friend/<str:username>/', add_friend, name='add_friend'),
    path('<str:username>/', ProfileView.as_view(), name='profile'),
    path('<str:username>/edit/', ProfileUpdateView.as_view(), name='profile_edit'),
    path('<str:username>/delete/', ProfileDeleteView.as_view(), name='profile_delete'),
]