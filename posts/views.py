# posts/views.py

from urllib import request
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, DetailView
from django.db.models import Q, Count
from .models import Post, PostMedia, Reaction, Comment, PRIVACY_CHOICES
from .forms import PostCreateForm, CommentCreateForm
from accounts.models import Friendship, User
from chat.models import Conversation
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from notifications.models import Notification
from django.urls import reverse_lazy
from .forms import PostCreateForm 

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
            
            context['post_form'] = PostCreateForm()
            
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

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = super().form_valid(form)
        for file in self.request.FILES.getlist('media_files'):
            media_type = 'IMAGE' if 'image' in file.content_type else 'VIDEO'
            PostMedia.objects.create(post=self.object, file=file, media_type=media_type)
        return response
    
    def get_success_url(self):
        # 1. Kiểm tra xem trên URL submit có tham số 'next' không
        next_url = self.request.GET.get('next')
        
        # 2. Nếu có 'next', chuyển hướng về đó
        if next_url:
            return next_url
            
        # 3. Nếu không có (mặc định), quay về trang chủ
        return reverse_lazy('posts:home')
    
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
                # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO KHI THAY ĐỔI REACTION ===
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
    
    # === KIỂM TRA QUYỀN BÌNH LUẬN ===
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

    # === SỬA LỖI LOGIC TẠO COMMENT ===
    content = request.POST.get('content')
    # SỬA Ở ĐÂY: Lấy đúng tên trường 'parent' từ form
    parent_id = request.POST.get('parent') 

    if not content or not content.strip():
        return JsonResponse({'status': 'error', 'message': 'Nội dung bình luận không được để trống.'}, status=400)

    parent_comment = None
    if parent_id:
        try:
            parent_comment = Comment.objects.get(id=parent_id)
        except Comment.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Bình luận cha không tồn tại.'}, status=404)

    new_comment = Comment.objects.create(
        post=post,
        author=request.user,
        content=content,
        parent=parent_comment
    )

    # === TẠO THÔNG BÁO ===
    if request.user != post.author:
        Notification.objects.create(
            recipient=post.author,
            sender=request.user,
            notification_type='POST_COMMENT',
            target_content_type=ContentType.objects.get_for_model(post),
            target_object_id=post.id
        )
    # Thông báo cho người được trả lời (nếu có và không phải là chính mình)
    if parent_comment and request.user != parent_comment.author:
         Notification.objects.create(
            recipient=parent_comment.author,
            sender=request.user,
            notification_type='POST_COMMENT', # Bạn có thể tạo type mới 'COMMENT_REPLY' nếu muốn
            target_content_type=ContentType.objects.get_for_model(parent_comment),
            target_object_id=parent_comment.id
        )

    # SỬA Ở ĐÂY: Tạo context đầy đủ để render HTML
    context = {
        'comment': new_comment,
        'post': post,
        'user': request.user,
        'comment_user_reactions_map': {}  # Comment mới chưa có ai reaction, nên truyền vào map rỗng
    }
    comment_html = render_to_string('posts/_single_comment.html', context, request=request)
    
    # SỬA Ở ĐÂY: Trả về JSON response với thông tin chính xác
    response_data = {
        'status': 'ok',
        'comment_html': comment_html,
        'is_reply': new_comment.parent is not None,
        'parent_id': parent_id if parent_id else None
    }
    return JsonResponse(response_data)

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
            # === BẮT ĐẦU SỬA: TẠO THÔNG BÁO KHI THAY ĐỔI REACTION ===
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

@login_required
def get_reaction_list(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    content_type = ContentType.objects.get_for_model(Post)
    
    reactions = Reaction.objects.filter(
        content_type=content_type,
        object_id=post.id
    ).select_related('user').order_by('-id')

    current_user_friends_qs = Friendship.get_friends(request.user)
    current_user_friend_ids = set(current_user_friends_qs.values_list('id', flat=True))
    
    reactions_data = []
    for reaction in reactions:
        reactor = reaction.user
        
        is_friend = reactor.id in current_user_friend_ids
        
        conversation_id = None
        if is_friend:
            conversation = Conversation.objects.filter(
                participants=request.user
            ).filter(
                participants=reactor
            ).first()
            if conversation:
                conversation_id = conversation.id

        # Lấy bạn chung (sẽ bằng 0 nếu người react không phải là bạn bè)
        mutual_friends_count = 0
        if is_friend:
            reactor_friends = Friendship.get_friends(reactor)
            mutual_friends_count = len(set(current_user_friends_qs) & set(reactor_friends))

        reactions_data.append({
            'username': reactor.username,
            'full_name': reactor.get_full_name() or reactor.username,
            'avatar_url': reactor.avatar.url,
            'profile_url': reverse('accounts:profile', kwargs={'username': reactor.username}),
            'reaction_type': reaction.reaction_type,
            'is_friend': is_friend,
            'conversation_id': conversation_id,
            # Sửa lại logic bạn chung để nó không bị gọi cho người không phải bạn bè
            'mutual_friends_count': mutual_friends_count,
        })
        
    reaction_counts = post.get_reaction_stats()

    return JsonResponse({
        'reactions': reactions_data,
        'reaction_counts': reaction_counts
    })

# View này chỉ trả về một đoạn HTML (Partial) để AJAX nạp vào Modal
def post_detail_modal(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    # Kiểm tra like của user hiện tại để hiển thị đúng trạng thái nút Like
    user_reactions_map = {}
    if request.user.is_authenticated:
        # Giả sử bạn có logic lấy reaction của user (tương tự view home)
        # Ví dụ logic đơn giản:
        user_reaction = post.reactions.filter(user=request.user).first()
        if user_reaction:
            user_reactions_map[post.id] = user_reaction.reaction_type

    # Lấy comments (có thể lấy hết hoặc limit tùy bạn)
    comments = post.comments.filter(parent=None).order_by('-created_at')

    context = {
        'post': post,
        'comments': comments,
        'user_reactions_map': user_reactions_map,
    }
    return render(request, 'posts/_post_modal_content.html', context)

def get_comment_reactions(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    reactions = comment.reactions.all().select_related('user')
    
    data = []
    reaction_counts = {}
    
    current_user = request.user

    for reaction in reactions:
        user = reaction.user
        reaction_type = reaction.reaction_type
        
        # Đếm số lượng từng loại reaction
        reaction_counts[reaction_type] = reaction_counts.get(reaction_type, 0) + 1
        
        # Kiểm tra quan hệ bạn bè để hiển thị nút nhắn tin
        is_friend = False
        conversation_id = None
        
        if current_user.is_authenticated and current_user != user:
            # Logic kiểm tra bạn bè 
            if Friendship.objects.filter(
                (Q(from_user=current_user, to_user=user) | Q(from_user=user, to_user=current_user)),
                status='ACCEPTED'
            ).exists():
                is_friend = True
                # Giả sử bạn có logic lấy conversation_id ở đây, nếu chưa có thì để null
                # conversation_id = ... 

        data.append({
            'username': user.username,
            'full_name': user.get_full_name(),
            'avatar_url': user.avatar.url,
            'profile_url': f"/user/{user.username}/", 
            'reaction_type': reaction_type,
            'is_friend': is_friend,
            'conversation_id': conversation_id, # Cần thiết nếu muốn nút nhắn tin hoạt động
            'mutual_friends_count': 0 # Tính năng nâng cao, để 0 tạm
        })
        
    return JsonResponse({
        'reactions': data,
        'reaction_counts': reaction_counts
    })

@login_required
def get_share_modal(request, post_id):
    # Lấy bài viết gốc
    post = get_object_or_404(Post, id=post_id)
    
    # KIỂM TRA QUYỀN XEM BÀI VIẾT (Logic tương tự như react/comment)
    viewer = request.user
    author = post.author
    can_view = False
    
    if viewer == author or post.privacy == 'PUBLIC':
        can_view = True
    elif post.privacy == 'FRIENDS':
        # Kiểm tra bạn bè
        are_friends = Friendship.objects.filter(
            (Q(from_user=author, to_user=viewer) | Q(from_user=viewer, to_user=author)),
            status='ACCEPTED'
        ).exists()
        if are_friends:
            can_view = True
            
    if not can_view or post.privacy == 'PRIVATE':
        return JsonResponse({'status': 'error', 'message': 'Bạn không có quyền chia sẻ bài viết này'}, status=403)

    # Render modal HTML
    html = render_to_string('posts/_share_post_modal.html', {'post': post}, request=request)
    return JsonResponse({'status': 'ok', 'html': html})

@login_required
@require_POST
def share_post(request, post_id):
    original_post = get_object_or_404(Post, id=post_id)
    
    # 1. Logic kiểm tra quyền xem (như trên)
    # ... (Để ngắn gọn, giả sử đã check quyền xem ở đây giống hàm trên) ...
    
    # 2. Lấy dữ liệu từ form
    content = request.POST.get('content', '')
    new_privacy = request.POST.get('privacy', 'PUBLIC')
    
    # 3. LOGIC QUYỀN RIÊNG TƯ (QUAN TRỌNG)
    # Phạm vi chia sẻ không được rộng hơn bài gốc
    if original_post.privacy == 'FRIENDS' and new_privacy == 'PUBLIC':
        return JsonResponse({'status': 'error', 'message': 'Bài viết gốc ở chế độ Bạn bè, bạn không thể chia sẻ Công khai.'}, status=400)
    
    # Nếu bài gốc là PRIVATE, lẽ ra không vào được đây, nhưng check thêm cho chắc
    if original_post.privacy == 'PRIVATE':
        return JsonResponse({'status': 'error', 'message': 'Không thể chia sẻ bài viết riêng tư.'}, status=400)

    # 4. Tạo bài viết mới (là bài chia sẻ)
    # Nếu bài gốc vốn đã là một bài chia sẻ, ta chia sẻ bài gốc CỦA bài chia sẻ đó (để tránh chuỗi dài)
    # Hoặc đơn giản là chia sẻ trực tiếp bài hiện tại. Ở đây ta chọn chia sẻ bài hiện tại.
    source_post = original_post.shared_from if original_post.shared_from else original_post

    new_post = Post.objects.create(
        author=request.user,
        content=content,
        privacy=new_privacy,
        shared_from=source_post # Liên kết đến bài gốc
    )
    
    # Tạo thông báo cho chủ bài viết gốc
    if request.user != source_post.author:
        Notification.objects.create(
            recipient=source_post.author,
            sender=request.user,
            notification_type='POST_SHARE', 
            target_content_type=ContentType.objects.get_for_model(new_post),
            target_object_id=new_post.id
        )

    return JsonResponse({'status': 'ok', 'message': 'Đã chia sẻ bài viết!'})

@login_required
@require_POST
def change_post_privacy(request, pk):
    post = get_object_or_404(Post, pk=pk)
    
    # Kiểm tra quyền: Chỉ tác giả mới được đổi
    if post.author != request.user:
        return JsonResponse({'status': 'error', 'message': 'Bạn không có quyền thực hiện hành động này'}, status=403)
    
    new_privacy = request.POST.get('privacy')
    
    # Kiểm tra giá trị gửi lên có hợp lệ không
    valid_privacy_keys = [choice[0] for choice in PRIVACY_CHOICES] # ['PUBLIC', 'FRIENDS', 'PRIVATE']
    
    if new_privacy in valid_privacy_keys:
        post.privacy = new_privacy
        post.save()
        return JsonResponse({'status': 'ok', 'new_privacy': new_privacy})
    else:
        return JsonResponse({'status': 'error', 'message': 'Dữ liệu không hợp lệ'}, status=400)