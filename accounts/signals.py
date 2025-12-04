# accounts/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Friendship, User
from notifications.models import Notification

@receiver(post_save, sender=Friendship)
def create_friend_request_notification(sender, instance, created, **kwargs):
    # Tự động tạo thông báo khi một lời mời kết bạn (Friendship) được tạo
    # Chỉ chạy khi một bản ghi MỚI được tạo và có status là PENDING
    if created and instance.status == 'PENDING':
        # Tạo thông báo
        Notification.objects.create(
            recipient=instance.to_user,
            sender=instance.from_user,
            notification_type='FRIEND_REQUEST',
            target_content_type=ContentType.objects.get_for_model(instance),
            target_object_id=instance.id,
        )