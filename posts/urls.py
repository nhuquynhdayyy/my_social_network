# posts/urls.py

from django.urls import path
from .views import (
    HomePageView, PostCreateView, PostDeleteView, PostUpdateView, PostDetailView,
    react_to_post, add_comment, delete_comment, get_comment_edit_form, edit_comment, load_more_comments, get_reaction_list,
    post_detail_modal
)
from . import views

app_name = 'posts'

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    path('post/new/', PostCreateView.as_view(), name='post_create'),
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
    path('post/<int:post_id>/reactions/', get_reaction_list, name='get_reaction_list'),
    path('post/<int:post_id>/modal/', views.post_detail_modal, name='post_detail_modal'),
    path('comment/<int:comment_id>/reactions/', views.get_comment_reactions, name='comment_reactions'),
    path('post/<int:post_id>/get-share-modal/', views.get_share_modal, name='get_share_modal'),
    path('post/<int:post_id>/share/', views.share_post, name='share_post'),
    path('post/<int:pk>/change-privacy/', views.change_post_privacy, name='change_post_privacy'),
    path('post/<int:pk>/get-edit-form/', views.get_post_edit_form, name='get_post_edit_form'),
    path('tag/<str:slug>/', views.PostByTagListView.as_view(), name='tag_detail'),
    path('saved/', views.SavedPostsView.as_view(), name='saved_posts'),
    path('post/<int:post_id>/save/', views.save_post, name='save_post'),
    path('post/<int:post_id>/report/', views.report_post, name='report_post'),
]