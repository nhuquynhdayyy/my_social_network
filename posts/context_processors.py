# posts/context_processors.py
from django.db.models import Count
from .models import Tag
from django.utils import timezone
from datetime import timedelta

def trending_tags_processor(request):
    # Lấy bài trong 24h qua
    time_threshold = timezone.now() - timedelta(days=1)
    
    trending_tags = Tag.objects.filter(
        posts__created_at__gte=time_threshold
    ).annotate(
        num_posts=Count('posts')
    ).order_by('-num_posts')[:5]
    
    return {'trending_tags': trending_tags}