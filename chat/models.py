import os
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation

class Conversation(models.Model):
    CONVERSATION_TYPES = [
        ('PRIVATE', 'Cá nhân'),
        ('GROUP', 'Nhóm'),
    ]
    type = models.CharField(max_length=10, choices=CONVERSATION_TYPES, default='PRIVATE')
    name = models.CharField(max_length=128, blank=True, null=True)
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_groups')
    avatar = models.ImageField(upload_to='group_avatars/', default='group_default.png')
    admin_only_management = models.BooleanField(default=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    updated_at = models.DateTimeField(auto_now=True)
    last_message = models.ForeignKey(
        'Message',
        related_name='+',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    def __str__(self):
        return f"Conversation {self.id}"

class GroupMembershipRequest(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='membership_requests')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invitations_sent')
    user_to_add = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_invitations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('conversation', 'user_to_add')

    def __str__(self):
        return f"{self.invited_by} invited {self.user_to_add} to {self.conversation}"
    
class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages', null=True, blank=True)
    
    # Text có thể trống nếu gửi ảnh/video
    text = models.TextField(blank=True, null=True) 
    # === THÊM TRƯỜNG FILE ===
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    # ========================

    timestamp = models.DateTimeField(auto_now_add=True)
    reactions = GenericRelation('posts.Reaction')
    
    hidden_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='hidden_messages', blank=True)
    
    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        sender_name = self.sender.username if self.sender else "System"
        return f"Message from {sender_name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    # Helpers kiểm tra loại file
    @property
    def is_image(self):
        if not self.file: return False
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic']

    @property
    def is_video(self):
        if not self.file: return False
        ext = os.path.splitext(self.file.name)[1].lower()
        return ext in ['.mp4', '.mov', '.avi', '.wmv', '.mkv', '.webm']
    
class MessageReadStatus(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_messages')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user.username} read message {self.message.id}"