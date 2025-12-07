from django.contrib import admin
from django.urls import path, include  
from django.conf import settings 
from django.conf.urls.static import static 
from core import views 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')), 
    path('', include('posts.urls')),
    path('chat/', include('chat.urls', namespace='chat')),
    path('notifications/', include('notifications.urls')),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('redirect-after-login/', views.redirect_after_login, name='redirect_after_login'),
    path('dashboard/report/<int:report_id>/handle/', views.handle_report, name='handle_report'),
]

# Cấu hình để Django phục vụ các file media (như avatar) trong môi trường phát triển
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)