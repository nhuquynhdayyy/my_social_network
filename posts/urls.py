# posts/urls.py

from django.urls import path
from .views import HomePageView, PostCreateView, PostDeleteView, PostUpdateView

urlpatterns = [
    # Khi người dùng truy cập vào URL gốc của app này (''),
    # hãy gọi HomePageView
    path('', HomePageView.as_view(), name='home'),
    # URL cho trang tạo bài viết
    path('post/new/', PostCreateView.as_view(), name='post_create'),
    # URL cho trang xóa bài viết
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post_delete'),
    # URL cho trang chỉnh sửa bài viết
    path('post/<int:pk>/edit/', PostUpdateView.as_view(), name='post_edit'),
]