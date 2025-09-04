# core/urls.py

from django.contrib import admin
from django.urls import path, include  # Thêm 'include'
from django.conf import settings # Thêm
from django.conf.urls.static import static # Thêm

urlpatterns = [
    path('admin/', admin.site.urls),
    # Khi người dùng truy cập vào trang web với đường dẫn rỗng (''),
    # hãy chuyển hướng tất cả các yêu cầu còn lại cho file urls.py của app 'posts' xử lý.
    path('accounts/', include('accounts.urls')), # Thêm dòng này
    path('', include('posts.urls')),
    path('chat/', include('chat.urls', namespace='chat')),
]

# Cấu hình để Django phục vụ các file media (như avatar) trong môi trường phát triển
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)