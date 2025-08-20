# accounts/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, UpdateView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin # Thêm Mixins
from django.contrib.auth.decorators import login_required
from django.db.models import Q # Dùng Q object cho truy vấn phức tạp
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User, Friendship # Import User model

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    # reverse_lazy sẽ đợi cho đến khi URL được load xong
    success_url = reverse_lazy('accounts:login') # Chuyển hướng đến trang đăng nhập sau khi đăng ký thành công
    template_name = 'accounts/register.html'

# View để xem Profile
class ProfileView(DetailView):
    model = User
    template_name = 'accounts/profile.html'
    context_object_name = 'profile_user' # Đặt tên biến trong template cho dễ hiểu

    # Lấy user object dựa trên username trong URL
    def get_object(self, queryset=None):
        return User.objects.get(username=self.kwargs.get('username'))

# View để chỉnh sửa Profile
class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'accounts/profile_edit.html'
    
    # Lấy user object dựa trên username trong URL
    def get_object(self, queryset=None):
        return User.objects.get(username=self.kwargs.get('username'))
    
    # Kiểm tra quyền: user đang đăng nhập có phải là chủ của profile này không
    def test_func(self):
        return self.get_object() == self.request.user

    # URL để chuyển hướng sau khi cập nhật thành công
    def get_success_url(self):
        return reverse_lazy('accounts:profile', kwargs={'username': self.request.user.username})

# View để xóa tài khoản
class ProfileDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'accounts/profile_confirm_delete.html'
    # Chuyển hướng về trang chủ sau khi xóa thành công
    success_url = reverse_lazy('home')

    # Lấy user object dựa trên username trong URL
    def get_object(self, queryset=None):
        return User.objects.get(username=self.kwargs.get('username'))
    
    # Kiểm tra quyền: user đang đăng nhập có phải là chủ của profile này không
    def test_func(self):
        return self.get_object() == self.request.user

# View hiển thị danh sách tất cả User
class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        # Lấy tất cả user trừ user đang đăng nhập
        return User.objects.exclude(username=self.request.user.username)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Tối ưu hóa: Lấy tất cả mối quan hệ bạn bè liên quan đến user hiện tại chỉ trong 1 lần truy vấn
        # để tránh N+1 query problem trong template.
        
        # 1. Danh sách ID của những người đã là bạn bè (status='ACCEPTED')
        friends_q = Friendship.objects.filter(
            (Q(from_user=user) | Q(to_user=user)) & Q(status='ACCEPTED')
        )
        friend_ids = set()
        for friendship in friends_q:
            friend_ids.add(friendship.from_user_id if friendship.to_user_id == user.id else friendship.to_user_id)
        
        # 2. Danh sách ID của những người mà user này đã gửi yêu cầu
        sent_request_ids = set(
            Friendship.objects.filter(from_user=user, status='PENDING').values_list('to_user_id', flat=True)
        )
        
        # 3. Danh sách ID của những người đã gửi yêu cầu cho user này
        received_request_ids = set(
            Friendship.objects.filter(to_user=user, status='PENDING').values_list('from_user_id', flat=True)
        )

        context['friend_ids'] = friend_ids
        context['sent_request_ids'] = sent_request_ids
        context['received_request_ids'] = received_request_ids
        
        return context

# Hàm xử lý logic gửi yêu cầu kết bạn
@login_required
def add_friend(request, username):
    to_user = get_object_or_404(User, username=username)
    from_user = request.user
    
    # Dùng get_or_create để tránh tạo trùng lặp yêu cầu
    # Chỉ tạo nếu chưa có mối quan hệ nào tồn tại giữa 2 người
    Friendship.objects.get_or_create(from_user=from_user, to_user=to_user)
    
    # Chuyển hướng người dùng quay lại trang danh sách
    return redirect('accounts:user_list')

# View để xem danh sách lời mời kết bạn
class FriendRequestListView(LoginRequiredMixin, ListView):
    model = Friendship
    template_name = 'accounts/friend_requests.html'
    context_object_name = 'friend_requests'

    def get_queryset(self):
        # Lấy tất cả các lời mời gửi đến user hiện tại và đang ở trạng thái PENDING
        return Friendship.objects.filter(to_user=self.request.user, status='PENDING')

# View để chấp nhận lời mời
@login_required
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    # Kiểm tra bảo mật: chỉ người nhận mới có quyền chấp nhận
    if friend_request.to_user == request.user:
        friend_request.status = 'ACCEPTED'
        friend_request.save()
        # (Tùy chọn) Có thể tạo thông báo "đã chấp nhận" gửi ngược lại
    return redirect('accounts:friend_requests')

# View để từ chối/xóa lời mời
@login_required
def decline_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    # Kiểm tra bảo mật: chỉ người nhận mới có quyền xóa
    if friend_request.to_user == request.user:
        friend_request.delete()
    return redirect('accounts:friend_requests')

# View để xem danh sách lời mời đã gửi
class SentRequestListView(LoginRequiredMixin, ListView):
    model = Friendship
    template_name = 'accounts/sent_requests.html'
    context_object_name = 'sent_requests'

    def get_queryset(self):
        # Lấy tất cả các lời mời do user hiện tại gửi đi và đang ở trạng thái PENDING
        return Friendship.objects.filter(from_user=self.request.user, status='PENDING')

# View để hủy lời mời đã gửi
@login_required
def cancel_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id)
    # Kiểm tra bảo mật: chỉ người gửi mới có quyền hủy
    if friend_request.from_user == request.user:
        friend_request.delete()
    return redirect('accounts:sent_requests') # Chuyển hướng về trang danh sách đã gửi