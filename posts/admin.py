from django.contrib import admin
from .models import Post, PostMedia, Comment, Reaction

# Hiển thị PostMedia ngay trong trang chỉnh sửa Post
class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 1 # Số lượng form inline hiển thị

class PostAdmin(admin.ModelAdmin):
    inlines = [PostMediaInline]
    list_display = ('author', 'content', 'privacy', 'created_at')

admin.site.register(Post, PostAdmin)
admin.site.register(Comment)
admin.site.register(Reaction)