from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Kế thừa AbstractUser đã có sẵn các trường username, password, email...
    # Chỉ cần thêm các trường mở rộng vào đây
    avatar = models.ImageField(default='default.jpg', upload_to='profile_images')
    cover_photo = models.ImageField(default='cover_default.jpg', upload_to='cover_images')
    bio = models.TextField(blank=True, null=True)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.username

class Friendship(models.Model):
    from_user = models.ForeignKey(User, related_name='friendship_creator_set', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='friend_set', on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('PENDING', 'Pending'), ('ACCEPTED', 'Accepted')], default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"{self.from_user} to {self.to_user} - {self.status}"