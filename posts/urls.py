# posts/urls.py (ĐÃ SỬA)

from django.urls import path
# SỬA Ở ĐÂY: Thêm PostDetailView vào import
from .views import (
    HomePageView, PostCreateView, PostDeleteView, PostUpdateView, PostDetailView,
    react_to_post, add_comment, delete_comment, get_comment_edit_form, edit_comment, load_more_comments
)
from . import views

app_name = 'posts'

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('post/new/', PostCreateView.as_view(), name='post_create'),
    
    # THÊM DÒNG NÀY VÀO: Đây chính là URL mà template đang tìm kiếm
    path('post/<int:pk>/', PostDetailView.as_view(), name='post_detail'),
    
    path('post/<int:pk>/delete/', PostDeleteView.as_view(), name='post_delete'),
    path('post/<int:pk>/edit/', PostUpdateView.as_view(), name='post_edit'),
    path('post/<int:post_id>/react/', react_to_post, name='react_to_post'),
    path("post/<int:pk>/reactions/detail/", views.reaction_detail, name="reaction_detail"),
    path('post/<int:post_id>/comment/', add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', delete_comment, name='delete_comment'),
    path('comment/<int:comment_id>/edit/', edit_comment, name='edit_comment'),
    path('comment/<int:comment_id>/get-edit-form/', get_comment_edit_form, name='get_comment_edit_form'),
    path('comment/<int:comment_id>/react/', views.react_to_comment, name='react_to_comment'), 
    path('post/<int:pk>/load-comments/', load_more_comments, name='load_more_comments'),
]