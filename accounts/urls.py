from django.urls import path
from django.contrib.auth import views as auth_views
from .forms import UserLoginForm 
from .views import (
    SignUpView, activate, ProfileView, ProfileUpdateView, ProfileDeleteView,
    UserListView, add_friend, 
    FriendRequestListView, accept_friend_request, decline_friend_request,
    SentRequestListView, cancel_friend_request,
    FriendListView, unfriend,
    forgot_password, reset_password_validate, reset_password
)

app_name = 'accounts'

urlpatterns = [
    path('register/', SignUpView.as_view(), name='register'),
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        authentication_form=UserLoginForm  
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', UserListView.as_view(), name='user_list'),

    path('forgotPassword/', forgot_password, name='forgotPassword'),
    path('reset_password_validate/<uidb64>/<token>/', reset_password_validate, name='reset_password_validate'),
    path('reset_password/', reset_password, name='reset_password'),

    path('requests/', FriendRequestListView.as_view(), name='friend_requests'),
    path('requests/sent/', SentRequestListView.as_view(), name='sent_requests'),
    path('requests/accept/<int:request_id>/', accept_friend_request, name='accept_request'),
    path('requests/decline/<int:request_id>/', decline_friend_request, name='decline_request'),
    path('requests/cancel/<int:request_id>/', cancel_friend_request, name='cancel_request'),

    path('unfriend/<str:username>/', unfriend, name='unfriend'),

    # CÁC URL ĐỘNG PHẢI ĐẶT BÊN DƯỚI
    # Chúng sẽ được kiểm tra sau khi các URL cụ thể ở trên không khớp
    path('add-friend/<str:username>/', add_friend, name='add_friend'),
    path('<str:username>/', ProfileView.as_view(), name='profile'),
    path('<str:username>/edit/', ProfileUpdateView.as_view(), name='profile_edit'),
    path('<str:username>/delete/', ProfileDeleteView.as_view(), name='profile_delete'),
    path('<str:username>/friends/', FriendListView.as_view(), name='friend_list'),
]