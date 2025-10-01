from django.contrib import admin
from django.urls import path, include  
from django.conf import settings 
from django.conf.urls.static import static 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')), 
    path('', include('posts.urls')),
    path('chat/', include('chat.urls', namespace='chat')),
]

# Cấu hình để Django phục vụ các file media (như avatar) trong môi trường phát triển
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)