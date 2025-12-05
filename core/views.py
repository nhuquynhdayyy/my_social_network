from django.shortcuts import render, redirect
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from posts.models import Post, Comment, Reaction
# from django.contrib.contenttypes.models import ContentType # Nếu cần query phức tạp hơn

User = get_user_model()

@login_required
def redirect_after_login(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')
    return redirect('posts:home')

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    # 1. Tăng trưởng người dùng (7 ngày qua)
    today = timezone.now().date()
    dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
    user_counts = []
    formatted_dates = []
    
    for date in dates:
        # Lọc theo ngày tham gia (date_joined)
        count = User.objects.filter(date_joined__date=date).count()
        user_counts.append(count)
        formatted_dates.append(date.strftime('%d/%m'))

    # 2. Tỷ lệ tương tác tổng quan
    total_posts = Post.objects.count()
    total_comments = Comment.objects.count()
    total_reactions = Reaction.objects.count()

    # 3. Xếp hạng KOL (Top 5 user chăm chỉ nhất)
    # Lưu ý: Nếu model Post không có related_name='posts', hãy dùng 'post_set'
    top_users = User.objects.annotate(num_posts=Count('posts')).order_by('-num_posts')[:5]
    
    # 4. Top 5 Bài viết nhiều cảm xúc nhất
    # Lưu ý: Để dòng này chạy, Model Post cần có GenericRelation hoặc related query phù hợp.
    # Nếu Reaction dùng GenericForeignKey, ta đếm thủ công hoặc dùng ContentType (phức tạp hơn).
    # Ở đây mình giả định bạn chưa cài GenericRelation, nên dùng cách thủ công an toàn hơn:
    
    # Cách an toàn: Lấy top post và đếm (Chỉ hiệu quả với data nhỏ/trung bình)
    # Nếu data lớn, cần thêm trường 'reaction_count' vào model Post để tối ưu.
    top_posts_raw = Post.objects.all()
    # Sắp xếp thủ công bằng Python (chậm hơn DB nhưng chắc chắn chạy không lỗi logic GFK)
    top_posts = sorted(top_posts_raw, key=lambda p: p.reactions.count(), reverse=True)[:5]
    
    # Nếu bạn đã cấu hình Reverse Relation trong GenericRelation ở model Post, 
    # bạn có thể dùng: Post.objects.annotate(total_reacts=Count('reactions')).order_by('-total_reacts')[:5]

    context = {
        'dates': formatted_dates,
        'user_counts': user_counts,
        'total_posts': total_posts,
        'total_comments': total_comments,
        'total_reactions': total_reactions,
        'top_users': top_users,
        'top_posts': top_posts,
    }
    return render(request, 'admin_dashboard.html', context)