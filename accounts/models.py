# accounts/models.py 

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import Q

# Lấy User model một cách linh hoạt
User = AbstractUser

class User(AbstractUser):
    # Kế thừa AbstractUser đã có sẵn các trường username, password, email...
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
    
    @staticmethod
    def get_friends(user):
        """
        Trả về một danh sách các đối tượng User là bạn của `user` được cung cấp.
        """
        friend_ids = set()
        # Query để lấy các mối quan hệ 'ACCEPTED' mà user có tham gia
        friendships = Friendship.objects.filter(
            (Q(from_user=user) | Q(to_user=user)) & Q(status='ACCEPTED')
        )
        # Lặp qua các mối quan hệ để lấy ra ID của người bạn
        for f in friendships:
            friend_ids.add(f.to_user.id if f.from_user == user else f.from_user.id)
        
        # Trả về một QuerySet các đối tượng User từ danh sách ID đã thu thập
        return User.objects.filter(id__in=friend_ids)