# posts/views.py

from django.shortcuts import render
from django.views.generic import ListView
from .models import Post

class HomePageView(ListView):
    model = Post  # Model mà View này sẽ làm việc cùng
    template_name = 'posts/home.html'  # Đường dẫn tới file template sẽ được sử dụng
    context_object_name = 'posts'  # Tên của biến chứa danh sách bài đăng trong template

    def get_queryset(self):
        # Tạm thời, chúng ta sẽ hiển thị tất cả bài đăng công khai
        # Sau này, bạn sẽ thay đổi logic này để chỉ hiển thị bài của bạn bè
        return Post.objects.filter(privacy='PUBLIC').order_by('-created_at')