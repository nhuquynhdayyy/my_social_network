# posts/urls.py

from django.urls import path
from .views import HomePageView, PostCreateView, PostDeleteView, PostUpdateView, react_to_post, add_comment, delete_comment, get_comment_edit_form, edit_comment
from . import views

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
    # URL cho hành động thả cảm xúc
    path('post/<int:post_id>/react/', react_to_post, name='react_to_post'),
    path("post/<int:pk>/reactions/detail/", views.reaction_detail, name="reaction_detail"),
    # URL cho comment
    path('post/<int:post_id>/comment/', add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete_comment'),
    # URLs cho việc sửa bình luận
    path('comment/<int:comment_id>/edit/', edit_comment, name='edit_comment'),
    path('comment/<int:comment_id>/get-edit-form/', get_comment_edit_form, name='get_comment_edit_form'),
]