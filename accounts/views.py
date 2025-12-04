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
from .models import User, Friendship 
from posts.models import Post, Reaction, Comment 
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.http import HttpResponse
from .tokens import account_activation_token 
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from posts.forms import PostCreateForm

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'

    def form_valid(self, form):
        # Lưu user nhưng chưa commit vào DB để chỉnh sửa
        user = form.save(commit=False)
        user.is_active = False # Vô hiệu hóa tài khoản chưa kích hoạt email 
        user.save() # Lưu user vào DB với is_active=False

        # Gửi email xác thực
        current_site = get_current_site(self.request)
        mail_subject = 'Kích hoạt tài khoản của bạn.'
        message = render_to_string('accounts/acc_active_email.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        to_email = form.cleaned_data.get('email')
        email = EmailMessage(
            mail_subject, message, to=[to_email]
        )
        email.send()

        # Trả về trang thông báo yêu cầu check mail
        return render(self.request, 'accounts/email_sent_confirm.html')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return render(request, 'accounts/activation_complete.html') # Trang báo thành công
    else:
        return HttpResponse('Link kích hoạt không hợp lệ hoặc đã hết hạn!')

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

        # === 1. LOGIC LẤY BÀI VIẾT ===
        if visitor.is_authenticated and visitor == profile_user:
            queryset = Post.objects.filter(author=profile_user)
        else:
            queryset = Post.objects.filter(author=profile_user, privacy='PUBLIC')
            if visitor.is_authenticated:
                # Kiểm tra bạn bè để hiện bài viết FRIENDS
                are_friends_check = Friendship.objects.filter(
                    (Q(from_user=profile_user, to_user=visitor) | Q(from_user=visitor, to_user=profile_user)),
                    status='ACCEPTED'
                ).exists()
                if are_friends_check:
                    queryset = Post.objects.filter(
                        author=profile_user, 
                        privacy__in=['PUBLIC', 'FRIENDS']
                    )

        context['post_form'] = PostCreateForm() 
        context['posts'] = queryset.order_by('-created_at')

        # === 2. LOGIC KIỂM TRA TRẠNG THÁI BẠN BÈ ĐỂ HIỂN THỊ NÚT (THÊM MỚI ĐOẠN NÀY) ===
        is_friend = False
        sent_request = False
        received_request = False

        if visitor.is_authenticated and visitor != profile_user:
            # Kiểm tra đã là bạn chưa
            if Friendship.objects.filter(
                (Q(from_user=visitor, to_user=profile_user) | Q(from_user=profile_user, to_user=visitor)),
                status='ACCEPTED'
            ).exists():
                is_friend = True
            
            # Kiểm tra mình đã gửi lời mời chưa
            elif Friendship.objects.filter(from_user=visitor, to_user=profile_user, status='PENDING').exists():
                sent_request = True
            
            # Kiểm tra họ đã gửi lời mời cho mình chưa
            elif Friendship.objects.filter(from_user=profile_user, to_user=visitor, status='PENDING').exists():
                received_request = True
        
        # Truyền biến vào template
        context['is_friend'] = is_friend
        context['sent_request'] = sent_request
        context['received_request'] = received_request

        # === 3. LOGIC REACTION MAP ===
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
        
        # --- Logic xác định trạng thái bạn bè ---
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
        
        # --- Truyền từ khóa tìm kiếm ra template để giữ lại trong ô input ---
        context['query'] = self.request.GET.get('q', '') 
        
        return context

@login_required
def add_friend(request, username):
    to_user = get_object_or_404(User, username=username)
    from_user = request.user
    Friendship.objects.get_or_create(from_user=from_user, to_user=to_user)
    # === LOGIC CHUYỂN HƯỚNG ===
    # 1. Kiểm tra xem URL có gửi kèm tham số 'next' không
    next_url = request.GET.get('next')
    
    # 2. Nếu có, chuyển hướng về trang đang đứng
    if next_url:
        return redirect(next_url)
        
    # 3. Nếu không (mặc định), về trang danh sách tìm bạn
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
            # Target để khi click vào sẽ tới trang cá nhân của người chấp nhận
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

    # === LOGIC CHUYỂN HƯỚNG ===
    # 1. Kiểm tra xem URL có gửi kèm tham số 'next' không
    next_url = request.GET.get('next')
    
    # 2. Nếu có 'next', chuyển hướng về trang đang đứng
    if next_url:
        return redirect(next_url)
    
    # 3. Nếu không có (fallback), mặc định về trang cá nhân của người bị hủy
    return redirect('accounts:profile', username=friend_to_remove.username)

# --- PHẦN FORGOT PASSWORD & RESET PASSWORD ---

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email__exact=email)

            # Tạo nội dung email
            current_site = get_current_site(request)
            mail_subject = 'Yêu cầu đặt lại mật khẩu'
            
            message = render_to_string('accounts/reset_password_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'Vui lòng kiểm tra email để đặt lại mật khẩu.')
            return redirect('accounts:login') 
        else:
            messages.error(request, 'Email không tồn tại trong hệ thống!')
            return redirect('accounts:forgotPassword')

    return render(request, 'accounts/forgot_password.html')

def reset_password_validate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Xác thực thành công, vui lòng nhập mật khẩu mới.')
        return redirect('accounts:reset_password')
    else:
        messages.error(request, 'Đường dẫn đã hết hạn hoặc không hợp lệ!')
        return redirect('accounts:forgotPassword')

def reset_password(request):
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if password != confirm_password:
            messages.error(request, 'Mật khẩu xác nhận không khớp!')
            return redirect('accounts:reset_password')
        
        uid = request.session.get('uid')
        if not uid:
            messages.error(request, 'Phiên làm việc hết hạn, vui lòng thử lại.')
            return redirect('accounts:forgotPassword')
            
        try:
            user = User.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            
            del request.session['uid']
            
            messages.success(request, 'Đổi mật khẩu thành công, vui lòng đăng nhập lại.')
            return redirect('accounts:login')
        except:
             messages.error(request, 'Đã có lỗi xảy ra.')
             return redirect('accounts:reset_password')

    return render(request, 'accounts/reset_password.html')