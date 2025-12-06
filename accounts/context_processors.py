# accounts/context_processors.py

from .models import Friendship, User
from django.db.models import Q, Count
from posts.models import Tag
from django.utils import timezone
from datetime import timedelta

def friends_sidebar_processor(request):
    # Cung cấp danh sách bạn bè cho sidebar bên phải trên mọi trang
    # Chỉ xử lý nếu người dùng đã đăng nhập
    if request.user.is_authenticated:
        current_user = request.user
        
        # Lấy ID của tất cả bạn bè
        friendships = Friendship.objects.filter(
            (Q(from_user=current_user) | Q(to_user=current_user)) & Q(status='ACCEPTED')
        )
        
        friend_ids = []
        for friendship in friendships:
            if friendship.from_user == current_user:
                friend_ids.append(friendship.to_user.id)
            else:
                friend_ids.append(friendship.from_user.id)
        
        # Lấy các đối tượng User của bạn bè, giới hạn 7 người để sidebar không quá dài
        sidebar_friends_list = User.objects.filter(id__in=friend_ids).order_by('?')[:7]

        # Trả về một dictionary. Key của dictionary này sẽ là tên biến trong template
        return {
            'sidebar_friends_list': sidebar_friends_list
        }
        
    # Nếu người dùng chưa đăng nhập, trả về dictionary rỗng
    return {}

def trending_tags_processor(request):
    # Lấy top 5 tag được dùng nhiều nhất trong 24h qua
    # Logic: Lọc các tag có bài viết (post) được tạo trong 24h qua -> Đếm -> Sắp xếp
    time_threshold = timezone.now() - timedelta(days=1)
    
    trending_tags = Tag.objects.filter(
        posts__created_at__gte=time_threshold
    ).annotate(
        num_posts=Count('posts')
    ).order_by('-num_posts')[:5]
    
    return {'trending_tags': trending_tags}