# posts/views.py
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import ListView, CreateView
from .models import Post, PostMedia
from .forms import PostCreateForm 

class HomePageView(ListView):
    model = Post  # Model mà View này sẽ làm việc cùng
    template_name = 'posts/home.html'  # Đường dẫn tới file template sẽ được sử dụng
    context_object_name = 'posts'  # Tên của biến chứa danh sách bài đăng trong template

    def get_queryset(self):
        # Tạm thời, chúng ta sẽ hiển thị tất cả bài đăng công khai
        # Sau này, bạn sẽ thay đổi logic này để chỉ hiển thị bài của bạn bè
        return Post.objects.filter(privacy='PUBLIC').order_by('-created_at')

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