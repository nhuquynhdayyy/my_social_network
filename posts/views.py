# posts/views.py
from urllib import request
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, DeleteView, UpdateView
from django.db.models import Q, Count # Import Count để thống kê
from .models import Post, PostMedia, Reaction, Comment
from .forms import PostCreateForm, CommentCreateForm
from accounts.models import Friendship, User
import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string # Dùng để render HTML trong view
from notifications.models import Notification

class HomePageView(ListView):
    model = Post
    template_name = 'posts/home.html'
    context_object_name = 'posts'
    # Phân trang: hiển thị 10 bài viết mỗi trang
    paginate_by = 10 

    def get_queryset(self):
        # Lấy người dùng đang đăng nhập
        current_user = self.request.user

        # Queryset cơ sở: các bài viết công khai
        queryset = Post.objects.filter(privacy='PUBLIC')

        # Nếu người dùng đã đăng nhập, mở rộng queryset
        if current_user.is_authenticated:
            # 1. Lấy ID của tất cả bạn bè
            friends_q = Friendship.objects.filter(
                (Q(from_user=current_user) | Q(to_user=current_user)) & Q(status='ACCEPTED')
            )
            friend_ids = []
            for friendship in friends_q:
                friend_ids.append(friendship.from_user_id if friendship.to_user_id == current_user.id else friendship.to_user_id)

            # 2. Xây dựng các điều kiện lọc
            
            # Điều kiện 1: Bài viết của chính mình (bất kể privacy)
            my_posts = Q(author=current_user)
            
            # Điều kiện 2: Bài viết của bạn bè (với privacy là 'FRIENDS')
            friends_posts = Q(author_id__in=friend_ids, privacy='FRIENDS')
            
            # Điều kiện 3: Bài viết công khai (đã có trong queryset ban đầu)
            public_posts = Q(privacy='PUBLIC')
            
            # Kết hợp các điều kiện bằng phép toán OR (|)
            # Dùng distinct() để loại bỏ các bài viết bị trùng lặp (nếu có)
            queryset = Post.objects.filter(my_posts | friends_posts | public_posts).distinct().order_by('-created_at')

        return queryset


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Lấy ID các bài viết đang hiển thị trên trang hiện tại
            post_ids = [post.id for post in context['posts']]
            
            # 1. Lấy reaction của user cho các BÀI VIẾT (giữ nguyên như cũ)
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

            # === PHẦN BẠN CẦN THÊM VÀO ===
            # 2. Lấy reaction của user cho các BÌNH LUẬN thuộc các bài viết đó
            comment_content_type = ContentType.objects.get_for_model(Comment)
            
            # Lấy ID của tất cả các bình luận thuộc các bài viết đang hiển thị
            comment_ids = Comment.objects.filter(post_id__in=post_ids).values_list('id', flat=True)
            
            user_comment_reactions = Reaction.objects.filter(
                user=self.request.user,
                object_id__in=comment_ids,
                content_type=comment_content_type
            ).values('object_id', 'reaction_type')
            
            # Tạo một map riêng cho reaction của comment để template sử dụng
            context['comment_user_reactions_map'] = {
                reaction['object_id']: reaction['reaction_type']
                for reaction in user_comment_reactions
            }
            # === KẾT THÚC PHẦN THÊM VÀO ===
            
        return context
    
# View để tạo bài viết mới
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostCreateForm
    template_name = 'posts/post_form.html'
    success_url = reverse_lazy('home') # Chuyển về trang chủ sau khi đăng bài thành công

    def form_valid(self, form):
        # Gán author là user đang đăng nhập trước khi lưu form
        form.instance.author = self.request.user
        
        # Gọi super().form_valid(form) để lưu đối tượng Post và nhận lại response
        response = super().form_valid(form)
        
        # Xử lý các file media đã upload
        # self.object chính là đối tượng Post vừa được lưu
        for file in self.request.FILES.getlist('media_files'):
            # Giả định đơn giản, cần cải tiến để xác định video/image
            media_type = 'IMAGE' if 'image' in file.content_type else 'VIDEO'
            PostMedia.objects.create(post=self.object, file=file, media_type=media_type)
        
        return response
    
# View để xóa bài viết
class PostDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Post
    template_name = 'posts/post_confirm_delete.html'
    # Chuyển hướng về trang chủ sau khi xóa thành công
    success_url = reverse_lazy('home')

    # Hàm kiểm tra quyền: user đang đăng nhập có phải là tác giả của bài viết không
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author
    
# View để chỉnh sửa bài viết
class PostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Post
    form_class = PostCreateForm # Tái sử dụng form tạo bài viết
    template_name = 'posts/post_form_edit.html' # Dùng template mới để tùy chỉnh tiêu đề
    
    # Hàm kiểm tra quyền: user đang đăng nhập có phải là tác giả của bài viết không
    def test_func(self):
        post = self.get_object()
        return self.request.user == post.author

    # Chuyển hướng về trang chủ sau khi chỉnh sửa thành công
    def get_success_url(self):
        return reverse_lazy('home')
    
# View xử lý logic thả cảm xúc
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
