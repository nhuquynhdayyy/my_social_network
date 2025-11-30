from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('FRIEND_REQUEST', 'Yêu cầu kết bạn'),
        ('FRIEND_ACCEPT', 'Chấp nhận lời mời kết bạn'),
        ('POST_LIKE', 'Thích bài viết'),
        ('POST_COMMENT', 'Bình luận bài viết'),
        ('COMMENT_REACTION', 'Bày tỏ cảm xúc về bình luận'), 
        ('MESSAGE', 'Tin nhắn mới'),
        ('MESSAGE_REACTION', 'Bày tỏ cảm xúc về tin nhắn'),
        ('ADDED_TO_GROUP', 'Được thêm vào nhóm'),          
        ('GROUP_INVITE_REQUEST', 'Yêu cầu phê duyệt thành viên'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    target_object_id = models.PositiveIntegerField(null=True, blank=True)
    target = GenericForeignKey('target_content_type', 'target_object_id')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Notification for {self.recipient.username} from {self.sender.username}"