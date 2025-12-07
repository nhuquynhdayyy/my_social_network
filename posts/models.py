from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.urls import reverse
from django.conf import settings

PRIVACY_CHOICES = [
    ('PUBLIC', 'Công khai'),
    ('FRIENDS', 'Bạn bè'),
    ('PRIVATE', 'Chỉ mình tôi'),
]

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        # Đường dẫn để xem tất cả bài viết của tag này
        return reverse('posts:tag_detail', kwargs={'slug': self.name})
    
class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    privacy = models.CharField(max_length=10, choices=PRIVACY_CHOICES, default='PUBLIC')
    created_at = models.DateTimeField(auto_now_add=True)
    shared_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='shares')
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    
    reactions = GenericRelation('Reaction')
    def get_reaction_stats(self):
        stats = self.reactions.values('reaction_type').annotate(count=Count('id')).order_by('-count')
        return {item['reaction_type']: item['count'] for item in stats}
    
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post by {self.author.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def comment_count(self):
        # Trả về tổng số bình luận (chỉ tính bình luận gốc, không tính reply
        return self.comments.filter(parent__isnull=True).count()

    def get_initial_comments(self, limit=3):
        # Trả về các bình luận gốc gần nhất, giới hạn bởi `limit`
        return self.comments.filter(parent__isnull=True).order_by('-created_at')[:limit]
    
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
    
    reactions = GenericRelation('Reaction')
    def get_reaction_stats(self):
        stats = self.reactions.values('reaction_type').annotate(count=Count('id'))
        return {item['reaction_type']: item['count'] for item in stats}

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
    
class Report(models.Model):
    REPORT_REASONS = [
        ('SPAM', 'Spam/Tin rác'),
        ('INAPPROPRIATE', 'Nội dung không phù hợp'),
        ('HATE_SPEECH', 'Ngôn từ thù ghét'),
        ('VIOLENCE', 'Bạo lực'),
        ('OTHER', 'Lý do khác'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Chờ xử lý'),
        ('RESOLVED', 'Đã xử lý (Xóa bài)'),
        ('IGNORED', 'Bỏ qua (Không vi phạm)'),
    ]

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_sent')
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.post.id} by {self.reporter.username}"