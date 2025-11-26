# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin 
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth import get_user_model
from notifications.models import Notification 
from .forms import CustomUserCreationForm, CustomUserChangeForm
# ĐÃ SỬA: Bỏ FriendRequest khỏi dòng import dưới đây
from .models import User, Friendship 
from posts.models import Post, Reaction, Comment 
from django.contrib.contenttypes.models import ContentType

class SignUpView(CreateView):
    # ... (Giữ nguyên phần còn lại của file không thay đổi) ...
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('accounts:login') 
    template_name = 'accounts/register.html'

class ProfileView(DetailView):
    model = User
    template_name = 'accounts/profile.html'
    context_object_name = 'profile_user'

    def get_object(self, queryset=None):
        return get_object_or_404(User, username=self.kwargs.get('username'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        profile_user = self.get_object()
        visitor = self.request.user

        if visitor.is_authenticated and visitor == profile_user:
            queryset = Post.objects.filter(author=profile_user)
        else:
            queryset = Post.objects.filter(author=profile_user, privacy='PUBLIC')
            if visitor.is_authenticated:
                are_friends = Friendship.objects.filter(
                    (Q(from_user=profile_user, to_user=visitor) | Q(from_user=visitor, to_user=profile_user)),
                    status='ACCEPTED'
                ).exists()
                if are_friends:
                    queryset = Post.objects.filter(
                        author=profile_user, 
                        privacy__in=['PUBLIC', 'FRIENDS']
                    )

        context['posts'] = queryset.order_by('-created_at')
        
        if self.request.user.is_authenticated:
            posts_on_page = context['posts']
            post_ids = [post.id for post in posts_on_page]
            
            post_content_type = ContentType.objects.get_for_model(Post)
            user_post_reactions = Reaction.objects.filter(
                user=self.request.user, 
                object_id__in=post_ids,
                content_type=post_content_type
            ).values('object_id', 'reaction_type')
            
            context['user_reactions_map'] = {
                reaction['object_id']: reaction['reaction_type'] 
                for reaction in user_post_reactions
            }

            comment_ids = Comment.objects.filter(post_id__in=post_ids).values_list('id', flat=True)
            comment_content_type = ContentType.objects.get_for_model(Comment)
            
            user_comment_reactions = Reaction.objects.filter(
                user=self.request.user,
                object_id__in=comment_ids,
                content_type=comment_content_type
            ).values('object_id', 'reaction_type')
            
            context['comment_user_reactions_map'] = {
                reaction['object_id']: reaction['reaction_type']
                for reaction in user_comment_reactions
            }

        return context


class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'accounts/profile_edit.html'
    
    def get_object(self, queryset=None):
        return User.objects.get(username=self.kwargs.get('username'))
    
    def test_func(self):
        return self.get_object() == self.request.user

    def get_success_url(self):
        return reverse_lazy('accounts:profile', kwargs={'username': self.request.user.username})

class ProfileDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'accounts/profile_confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_object(self, queryset=None):
        return User.objects.get(username=self.kwargs.get('username'))
    
    def test_func(self):
        return self.get_object() == self.request.user

class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        # 1. Lấy queryset gốc: Loại trừ user hiện tại
        queryset = User.objects.exclude(id=self.request.user.id)
        
        # 2. Xử lý tìm kiếm
        query = self.request.GET.get('q') # Lấy tham số 'q' từ URL
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |       # Tìm theo username
                Q(first_name__icontains=query) |     # Tìm theo Tên
                Q(last_name__icontains=query)        # Tìm theo Họ
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # --- Logic xác định trạng thái bạn bè (Giữ nguyên code cũ của bạn) ---
        friends_q = Friendship.objects.filter(
            (Q(from_user=user) | Q(to_user=user)) & Q(status='ACCEPTED')
        )
        friend_ids = set()
        for friendship in friends_q:
            friend_ids.add(friendship.from_user_id if friendship.to_user_id == user.id else friendship.to_user_id)
        
        sent_request_ids = set(
            Friendship.objects.filter(from_user=user, status='PENDING').values_list('to_user_id', flat=True)
        )
        
        received_request_ids = set(
            Friendship.objects.filter(to_user=user, status='PENDING').values_list('from_user_id', flat=True)
        )

        context['friend_ids'] = friend_ids
        context['sent_request_ids'] = sent_request_ids
        context['received_request_ids'] = received_request_ids
        
        # --- THÊM: Truyền từ khóa tìm kiếm ra template để giữ lại trong ô input ---
        context['query'] = self.request.GET.get('q', '') 
        
        return context

@login_required
def add_friend(request, username):
    to_user = get_object_or_404(User, username=username)
    from_user = request.user
    Friendship.objects.get_or_create(from_user=from_user, to_user=to_user)
    return redirect('accounts:user_list')

class FriendRequestListView(LoginRequiredMixin, ListView):
    model = Friendship
    template_name = 'accounts/friend_requests.html'
    context_object_name = 'friend_requests'

    def get_queryset(self):
        return Friendship.objects.filter(to_user=self.request.user, status='PENDING')

@login_required
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    if friend_request.to_user == request.user:
        friend_request.status = 'ACCEPTED'
        friend_request.save()

        # Tạo thông báo cho người đã gửi lời mời
        Notification.objects.create(
            recipient=friend_request.from_user,  # Người nhận thông báo là người gửi lời mời
            sender=request.user,                   # Người gửi thông báo là người chấp nhận
            notification_type='FRIEND_ACCEPT',
            # Target là người bạn mới, để khi click vào sẽ tới trang cá nhân của họ
            target_content_type=ContentType.objects.get_for_model(request.user),
            target_object_id=request.user.id
        )
        
    return redirect('accounts:friend_requests')

@login_required
def decline_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    if friend_request.to_user == request.user:
        friend_request.delete()
    return redirect('accounts:friend_requests')

class SentRequestListView(LoginRequiredMixin, ListView):
    model = Friendship
    template_name = 'accounts/sent_requests.html'
    context_object_name = 'sent_requests'

    def get_queryset(self):
        return Friendship.objects.filter(from_user=self.request.user, status='PENDING')

@login_required
def cancel_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    if friend_request.from_user == request.user:
        friend_request.delete()
    return redirect('accounts:sent_requests')

class FriendListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/friend_list.html'
    context_object_name = 'friends'

    def get_queryset(self):
        profile_user = get_object_or_404(User, username=self.kwargs['username'])
        friendships = Friendship.objects.filter(
            (Q(from_user=profile_user) | Q(to_user=profile_user)) & Q(status='ACCEPTED')
        )
        friend_ids = []
        for friendship in friendships:
            if friendship.from_user == profile_user:
                friend_ids.append(friendship.to_user.id)
            else:
                friend_ids.append(friendship.from_user.id)
        return User.objects.filter(id__in=friend_ids)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_user'] = get_object_or_404(User, username=self.kwargs['username'])
        return context

@login_required
def unfriend(request, username):
    friend_to_remove = get_object_or_404(User, username=username)
    current_user = request.user
    friendship = get_object_or_404(
        Friendship,
        (Q(from_user=current_user, to_user=friend_to_remove) | Q(from_user=friend_to_remove, to_user=current_user))
        & Q(status='ACCEPTED')
    )
    friendship.delete()
    return redirect('accounts:friend_list', username=current_user.username)