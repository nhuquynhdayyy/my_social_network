# posts/views.py (ĐÃ SỬA)

from urllib import request
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
# SỬA Ở ĐÂY: Thêm DetailView
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, DetailView
from django.db.models import Q, Count
from .models import Post, PostMedia, Reaction, Comment
from .forms import PostCreateForm, CommentCreateForm
from accounts.models import Friendship, User
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from notifications.models import Notification

class HomePageView(ListView):
    model = Post
    template_name = 'posts/home.html'
    context_object_name = 'posts'
    paginate_by = 10 

    def get_queryset(self):
        current_user = self.request.user
        queryset = Post.objects.filter(privacy='PUBLIC')
        if current_user.is_authenticated:
            friends_q = Friendship.objects.filter(
                (Q(from_user=current_user) | Q(to_user=current_user)) & Q(status='ACCEPTED')
            )
            friend_ids = [
                f.from_user_id if f.to_user_id == current_user.id else f.to_user_id
                for f in friends_q
            ]
            my_posts = Q(author=current_user)
            friends_posts = Q(author_id__in=friend_ids, privacy='FRIENDS')
            public_posts = Q(privacy='PUBLIC')
            queryset = Post.objects.filter(my_posts | friends_posts | public_posts).distinct().order_by('-created_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            post_ids = [post.id for post in context['posts']]
            post_content_type = ContentType.objects.get_for_model(Post)
            user_post_reactions = Reaction.objects.filter(
                user=self.request.user, 
                object_id__in=post_ids,
                content_type=post_content_type
            ).values('object_id', 'reaction_type')
            
            context['user_reactions_map'] = {
                reaction['object_id']: reaction['reaction_type'] 
                for reaction in user_post_reactions
            }
            comment_content_type = ContentType.objects.get_for_model(Comment)
            comment_ids = Comment.objects.filter(post_id__in=post_ids).values_list('id', flat=True)
            user_comment_reactions = Reaction.objects.filter(
                user=self.request.user,
                object_id__in=comment_ids,
                content_type=comment_content_type
            ).values('object_id', 'reaction_type')
            
            context['comment_user_reactions_map'] = {
                reaction['object_id']: reaction['reaction_type']
                for reaction in user_comment_reactions
            }
        return context

# ==========================================================
# === THÊM CLASS VIEW MỚI NÀY VÀO ===
# ==========================================================
class PostDetailView(DetailView):
    model = Post
    template_name = 'posts/post_detail.html'
    context_object_name = 'post' # Tên biến trong template sẽ là 'post'

    # Bạn có thể thêm get_context_data ở đây nếu cần truyền thêm dữ liệu
    # Ví dụ: truyền map reaction cho bài viết và bình luận
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            post = self.get_object()
            
            # Lấy reaction của user cho bài viết này
            post_content_type = ContentType.objects.get_for_model(Post)
            user_post_reaction = Reaction.objects.filter(
                user=self.request.user, 
                object_id=post.id,
                content_type=post_content_type
            ).first()
            context['user_reactions_map'] = {post.id: user_post_reaction.reaction_type} if user_post_reaction else {}

            # Lấy reaction của user cho các bình luận của bài viết này
            comment_content_type = ContentType.objects.get_for_model(Comment)
            comment_ids = post.comments.values_list('id', flat=True)
            user_comment_reactions = Reaction.objects.filter(
                user=self.request.user,
                object_id__in=comment_ids,
                content_type=comment_content_type
            ).values('object_id', 'reaction_type')
            context['comment_user_reactions_map'] = {
                r['object_id']: r['reaction_type'] for r in user_comment_reactions
            }
        return context
# ==========================================================
# === KẾT THÚC PHẦN THÊM MỚI ===
# ==========================================================
    
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'posts/post_form.html'
    success_url = reverse_lazy('posts:home')

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        for file in self.request.FILES.getlist('media_files'):
            media_type = 'IMAGE' if 'image' in file.content_type else 'VIDEO'
            PostMedia.objects.create(post=self.object, file=file, media_type=media_type)
        return response
    
class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = 'posts/post_confirm_delete.html'
    success_url = reverse_lazy('posts:home')

    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'posts/post_form_edit.html'
    
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

    def get_success_url(self):
        return reverse_lazy('posts:home')

# ... Các view hàm khác giữ nguyên như cũ ...
# (react_to_post, reaction_detail, add_comment, v.v...)
# ... (Phần code còn lại của bạn giữ nguyên)
# ...
@login_required
@require_POST
def react_to_post(request, post_id):
    try:
        post = get_object_or_404(Post, id=post_id)
        data = json.loads(request.body)
        reaction_type = data.get('reaction_type')

        viewer = request.user
        author = post.author
        can_react = False

        if viewer == author: 
            can_react = True
        elif post.privacy == 'PUBLIC':
            can_react = True
        elif post.privacy == 'FRIENDS':
            are_friends = Friendship.objects.filter(
                (Q(from_user=author, to_user=viewer) | Q(from_user=viewer, to_user=author)),
                status='ACCEPTED'
            ).exists()
            if are_friends:
                can_react = True
        
        if not can_react:
            return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện hành động này'}, status=403)

        content_type = ContentType.objects.get_for_model(Post)
        existing_reaction = Reaction.objects.filter(
            user=viewer, content_type=content_type, object_id=post.id
        ).first()
        
        current_user_reaction = None
        if existing_reaction:
            if existing_reaction.reaction_type == reaction_type:
                existing_reaction.delete()
                current_user_reaction = None # Đã bỏ react
            else:
                existing_reaction.reaction_type = reaction_type
                existing_reaction.save()
                current_user_reaction = reaction_type
                # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO KHI THAY ĐỔI REACTION (Code gốc của bạn - Đã giữ lại) ===
                if viewer != author:
                    Notification.objects.create(
                        recipient=author, sender=viewer, notification_type='POST_REACTION',
                        target_content_type=content_type, target_object_id=post.id
                    )
                # === KẾT THÚC SỬA ===
        else:
            Reaction.objects.create(
                user=viewer,
                content_type=content_type,
                object_id=post.id,
                reaction_type=reaction_type
            )
            current_user_reaction = reaction_type
        
            # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO CHO REACTION BÀI VIẾT ===
            if viewer != author:
                Notification.objects.create(
                    recipient=author,
                    sender=viewer,
                    notification_type='POST_REACTION',
                    target_content_type=content_type,
                    target_object_id=post.id
                )
            # === KẾT THÚC SỬA ===
            
        reaction_stats = post.reactions.values('reaction_type').annotate(count=Count('id')).order_by('-count')
        stats_dict = {item['reaction_type']: item['count'] for item in reaction_stats}
        total_reactions = post.reactions.count()
        
        return JsonResponse({
            'status': 'ok',
            'total_reactions': total_reactions,
            'reaction_stats': stats_dict,
            'current_user_reaction': current_user_reaction # Reaction hiện tại của user
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def reaction_detail(request, pk):
    post = Post.objects.get(pk=pk)
    post_type = ContentType.objects.get_for_model(Post)

    reactions = Reaction.objects.filter(
        content_type=post_type,
        object_id=post.id
    )

    data = {}
    for reaction in reactions:
        data.setdefault(reaction.reaction_type, []).append(reaction.user.username)

    return JsonResponse(data)

# === CÁC VIEW XỬ LÝ COMMENT ===

@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentCreateForm(request.POST)

    # === KIỂM TRA QUYỀN BÌNH LUẬN (Tương tự Reaction) ===
    viewer = request.user
    author = post.author
    can_comment = False
    if viewer == author or post.privacy == 'PUBLIC':
        can_comment = True
    elif post.privacy == 'FRIENDS':
        are_friends = Friendship.objects.filter(
            (Q(from_user=author, to_user=viewer) | Q(from_user=viewer, to_user=author)),
            status='ACCEPTED'
        ).exists()
        if are_friends:
            can_comment = True
    
    if not can_comment:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền bình luận'}, status=403)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post

        # === PHẦN NÂNG CẤP: XỬ LÝ COMMENT TRẢ LỜI ===
        parent_id = request.POST.get('parent_id')
        if parent_id:
            try:
                parent_comment = Comment.objects.get(id=parent_id)
                comment.parent = parent_comment
            except Comment.DoesNotExist:
                # Nếu parent comment không tồn tại, bỏ qua
                pass
        # === KẾT THÚC PHẦN NÂNG CẤP ===

        comment.save()

        # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO CHO BÌNH LUẬN MỚI ===
        if request.user != post.author:
            Notification.objects.create(
                recipient=post.author,
                sender=request.user,
                notification_type='POST_COMMENT',
                target_content_type=ContentType.objects.get_for_model(post),
                target_object_id=post.id
            )
        # === KẾT THÚC SỬA ===

        context = {
            'comment': comment,
            'post': post, 
            'user': request.user # Truyền user để các điều kiện trong template hoạt động
        }
        comment_html = render_to_string('posts/_single_comment.html', context, request=request)
        
        # Trả về ID của parent để JS biết chèn reply vào đâu
        response_data = {
            'status': 'ok',
            'comment_html': comment_html,
            'is_reply': bool(parent_id),
            'parent_id': parent_id
        }
        return JsonResponse(response_data)
    else:
        return JsonResponse({'status': 'error', 'message': 'Bình luận không hợp lệ'}, status=400)

@login_required
@require_POST
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    # Chỉ tác giả bình luận hoặc chủ bài viết mới có quyền xóa
    if comment.author == request.user or comment.post.author == request.user:
        comment.delete()
        return JsonResponse({'status': 'ok'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền xóa'}, status=403)
        
# View cho việc sửa sẽ phức tạp hơn, chúng ta sẽ làm sau nếu bạn muốn

# View để lấy form chỉnh sửa (GET request) - Đã hoàn thiện
@login_required
def get_comment_edit_form(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    # Kiểm tra quyền: Chỉ tác giả bình luận mới có quyền lấy form sửa
    if comment.author != request.user:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện hành động này'}, status=403)
    
    # Render ra HTML cho form chỉnh sửa
    form_html = render_to_string('posts/_comment_edit_form.html', {'comment': comment}, request=request)
    return JsonResponse({'status': 'ok', 'form_html': form_html})

# View để xử lý dữ liệu chỉnh sửa (POST request) - Đã hoàn thiện
@login_required
@require_POST
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    # Kiểm tra quyền: Chỉ tác giả bình luận mới có quyền sửa
    if comment.author != request.user:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện hành động này'}, status=403)
        
    # Dùng form để validate dữ liệu thay vì lấy trực tiếp từ request.POST
    form = CommentCreateForm(request.POST, instance=comment)
    if form.is_valid():
        updated_comment = form.save()
        # SỬA Ở ĐÂY
        context = {
            'comment': updated_comment,
            'post': updated_comment.post,
            'user': request.user
        }
        comment_html = render_to_string('posts/_single_comment.html', context, request=request)
        return JsonResponse({'status': 'ok', 'comment_html': comment_html})
    else:
        # Trả về lỗi nếu form không hợp lệ (ví dụ: nội dung trống)
        return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ'}, status=400)
    
@login_required
@require_POST
def react_to_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    post = comment.post
    
    # ... (Phần kiểm tra quyền giữ nguyên như cũ) ...
    viewer = request.user
    author = post.author
    can_react = False
    if viewer == author or post.privacy == 'PUBLIC':
        can_react = True
    elif post.privacy == 'FRIENDS':
        if Friendship.objects.filter((Q(from_user=author, to_user=viewer) | Q(from_user=viewer, to_user=author)), status='ACCEPTED').exists():
            can_react = True
    
    if not can_react:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thực hiện hành động này'}, status=403)
    
    # === NÂNG CẤP LOGIC REACTION ===
    data = json.loads(request.body)
    reaction_type = data.get('reaction_type')

    # Kiểm tra xem reaction_type có hợp lệ không
    valid_reactions = [choice[0] for choice in Reaction.REACTION_CHOICES]
    if reaction_type not in valid_reactions:
        return JsonResponse({'status': 'error', 'message': 'Loại reaction không hợp lệ'}, status=400)

    content_type = ContentType.objects.get_for_model(Comment)
    existing_reaction = Reaction.objects.filter(
        user=viewer, content_type=content_type, object_id=comment.id
    ).first()

    current_user_reaction = None
    if existing_reaction:
        if existing_reaction.reaction_type == reaction_type:
            existing_reaction.delete()
            current_user_reaction = None
        else:
            existing_reaction.reaction_type = reaction_type
            existing_reaction.save()
            current_user_reaction = reaction_type
            # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO KHI THAY ĐỔI REACTION (Code gốc của bạn - Đã giữ lại) ===
            if viewer != comment.author:
                Notification.objects.create(
                    recipient=comment.author, sender=viewer, notification_type='COMMENT_REACTION',
                    target_content_type=content_type, target_object_id=comment.id
                )
            # === KẾT THÚC SỬA ===
    else:
        Reaction.objects.create(
            user=viewer, content_type=content_type, object_id=comment.id, reaction_type=reaction_type
        )
        current_user_reaction = reaction_type

        # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO CHO REACTION BÌNH LUẬN ===
        if viewer != comment.author:
            Notification.objects.create(
                recipient=comment.author,
                sender=viewer,
                notification_type='COMMENT_REACTION',
                target_content_type=content_type,
                target_object_id=comment.id
            )
        # === KẾT THÚC SỬA ===
        
    # === NÂNG CẤP PHẦN TRẢ VỀ ===
    # Thống kê chi tiết
    reaction_stats = comment.reactions.values('reaction_type').annotate(count=Count('id'))
    stats_dict = {item['reaction_type']: item['count'] for item in reaction_stats}
    total_reactions = comment.reactions.count()
        
    return JsonResponse({
        'status': 'ok',
        'total_reactions': total_reactions,
        'reaction_stats': stats_dict,
        'current_user_reaction': current_user_reaction
    })

@login_required
def load_more_comments(request, pk):
    post = get_object_or_404(Post, pk=pk)
    offset = int(request.GET.get('offset', 0))
    limit = 5  # Tải 5 bình luận mỗi lần bấm

    # Lấy các bình luận tiếp theo
    comments = post.comments.filter(parent__isnull=True).order_by('-created_at')[offset:offset + limit]

    if not comments:
        return JsonResponse({'html': '', 'has_more': False})

    # Lấy reaction map cho các bình luận sắp được render
    comment_ids = [c.id for c in comments]
    comment_content_type = ContentType.objects.get_for_model(Comment)
    user_comment_reactions = Reaction.objects.filter(
        user=request.user,
        object_id__in=comment_ids,
        content_type=comment_content_type
    ).values('object_id', 'reaction_type')
    
    comment_user_reactions_map = {
        r['object_id']: r['reaction_type'] for r in user_comment_reactions
    }

    # Render các bình luận ra HTML
    html = ""
    for comment in comments:
        context = {
            'comment': comment,
            'post': post,
            'user': request.user,
            'comment_user_reactions_map': comment_user_reactions_map
        }
        html += render_to_string('posts/_single_comment.html', context, request=request)
    
    # Kiểm tra xem còn bình luận để tải nữa không
    new_offset = offset + len(comments)
    has_more = post.comment_count > new_offset

    return JsonResponse({'html': html, 'has_more': has_more, 'new_offset': new_offset})
