from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation

class Conversation(models.Model):
    CONVERSATION_TYPES = [
        ('PRIVATE', 'Cá nhân'),
        ('GROUP', 'Nhóm'),
    ]
    type = models.CharField(max_length=10, choices=CONVERSATION_TYPES, default='PRIVATE')
    name = models.CharField(max_length=128, blank=True, null=True) # Tên cho group chat
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_groups')
    avatar = models.ImageField(upload_to='group_avatars/', default='group_default.png')
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

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    reactions = GenericRelation('posts.Reaction')
    
    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class MessageReadStatus(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_messages')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user.username} read message {self.message.id}"