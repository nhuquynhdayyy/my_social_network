from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

PRIVACY_CHOICES = [
    ('PUBLIC', 'Công khai'),
    ('FRIENDS', 'Bạn bè'),
    ('PRIVATE', 'Chỉ mình tôi'),
]

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='PUBLIC')
    created_at = models.DateTimeField(auto_now_add=True)
    shared_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='shares')
    
    reactions = GenericRelation('Reaction')
    def get_reaction_stats(self):
        stats = self.reactions.values('reaction_type').annotate(count=Count('id')).order_by('-count')
        return {item['reaction_type']: item['count'] for item in stats}
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post by {self.author.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
class PostMedia(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media')
    file = models.FileField(upload_to='post_media/')
    media_type = models.CharField(max_length=10, choices=[('IMAGE', 'Image'), ('VIDEO', 'Video')])
    upload_date = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0) 

    def __str__(self):
        return f"{self.media_type} for Post {self.post.id}"

class Comment(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post}"

class Reaction(models.Model):
    REACTION_CHOICES = [
        ('LIKE', 'Thích'),
        ('LOVE', 'Yêu thích'),
        ('HAHA', 'Haha'),
        ('WOW', 'Wow'),
        ('SAD', 'Buồn'),
        ('ANGRY', 'Phẫn nộ'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=10, choices=REACTION_CHOICES)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f"{self.user.username} reacted {self.reaction_type} on {self.content_object}"