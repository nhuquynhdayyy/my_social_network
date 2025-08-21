# posts/urls.py

from django.urls import path
from .views import HomePageView, PostCreateView

urlpatterns = [
    # Khi người dùng truy cập vào URL gốc của app này (''),
    # hãy gọi HomePageView
    path('', HomePageView.as_view(), name='home'),
    # URL cho trang tạo bài viết
    path('post/new/', PostCreateView.as_view(), name='post_create'),
]