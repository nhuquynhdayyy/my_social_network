# posts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Post, Tag
import re

@receiver(post_save, sender=Post)
def extract_hashtags(sender, instance, created, **kwargs):
    # Chỉ chạy khi bài viết được tạo hoặc cập nhật nội dung
    if instance.content:
        # Regex tìm các từ bắt đầu bằng # (ví dụ: #hanoi)
        hashtags = re.findall(r"#(\w+)", instance.content)
        
        # Xóa hết tag cũ để cập nhật lại (phòng trường hợp user sửa bài xóa tag)
        instance.tags.clear()
        
        for tag_name in hashtags:
            # Tạo tag mới nếu chưa có, hoặc lấy tag cũ nếu đã có
            tag_obj, _ = Tag.objects.get_or_create(name=tag_name.lower())
            instance.tags.add(tag_obj)