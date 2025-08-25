# posts/views.py
from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from django.db.models import Q
from .models import Post, PostMedia
from .forms import PostCreateForm
from accounts.models import Friendship, User

class HomePageView(ListView):
    model = Post
    template_name = 'posts/home.html'
    context_object_name = 'posts'
    # Phân trang: hiển thị 10 bài viết mỗi trang
    paginate_by = 10 

    def get_queryset(self):
        # Lấy người dùng đang đăng nhập
        current_user = self.request.user

        # Queryset cơ sở: các bài viết công khai
        queryset = Post.objects.filter(privacy='PUBLIC')

        # Nếu người dùng đã đăng nhập, mở rộng queryset
        if current_user.is_authenticated:
            # 1. Lấy ID của tất cả bạn bè
            friends_q = Friendship.objects.filter(
                (Q(from_user=current_user) | Q(to_user=current_user)) & Q(status='ACCEPTED')
            )
            friend_ids = []
            for friendship in friends_q:
                friend_ids.append(friendship.from_user_id if friendship.to_user_id == current_user.id else friendship.to_user_id)

            # 2. Xây dựng các điều kiện lọc
            
            # Điều kiện 1: Bài viết của chính mình (bất kể privacy)
            my_posts = Q(author=current_user)
            
            # Điều kiện 2: Bài viết của bạn bè (với privacy là 'FRIENDS')
            friends_posts = Q(author_id__in=friend_ids, privacy='FRIENDS')
            
            # Điều kiện 3: Bài viết công khai (đã có trong queryset ban đầu)
            public_posts = Q(privacy='PUBLIC')
            
            # Kết hợp các điều kiện bằng phép toán OR (|)
            # Dùng distinct() để loại bỏ các bài viết bị trùng lặp (nếu có)
            queryset = Post.objects.filter(my_posts | friends_posts | public_posts).distinct().order_by('-created_at')

        return queryset

# View để tạo bài viết mới
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'posts/post_form.html'
    success_url = reverse_lazy('home') # Chuyển về trang chủ sau khi đăng bài thành công

    def form_valid(self, form):
        # Gán author là user đang đăng nhập trước khi lưu form
        form.instance.author = self.request.user
        
        # Gọi super().form_valid(form) để lưu đối tượng Post và nhận lại response
        response = super().form_valid(form)
        
        # Xử lý các file media đã upload
        # self.object chính là đối tượng Post vừa được lưu
        for file in self.request.FILES.getlist('media_files'):
            # Giả định đơn giản, cần cải tiến để xác định video/image
            media_type = 'IMAGE' if 'image' in file.content_type else 'VIDEO'
            PostMedia.objects.create(post=self.object, file=file, media_type=media_type)
        
        return response
    
# View để xóa bài viết
class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = 'posts/post_confirm_delete.html'
    # Chuyển hướng về trang chủ sau khi xóa thành công
    success_url = reverse_lazy('home')

    # Hàm kiểm tra quyền: user đang đăng nhập có phải là tác giả của bài viết không
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
# View để chỉnh sửa bài viết
class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostCreateForm # Tái sử dụng form tạo bài viết
    template_name = 'posts/post_form_edit.html' # Dùng template mới để tùy chỉnh tiêu đề
    
    # Hàm kiểm tra quyền: user đang đăng nhập có phải là tác giả của bài viết không
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

    # Chuyển hướng về trang chủ sau khi chỉnh sửa thành công
    def get_success_url(self):
        return reverse_lazy('home')