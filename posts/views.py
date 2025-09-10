# posts/views.py
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
        
        # ... (Phần kiểm tra reaction_type và kiểm tra quyền giữ nguyên như cũ) ...
        # === KIỂM TRA QUYỀN (PERMISSION CHECKING) ===
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


        # === XỬ LÝ LOGIC REACTION (giữ nguyên) ===
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
        
        # === THỐNG KÊ CHI TIẾT REACTION (PHẦN NÂNG CẤP) ===
        reaction_stats = post.reactions.values('reaction_type').annotate(count=Count('id')).order_by('-count')
        
        # Chuyển kết quả queryset thành một dict dễ dùng hơn
        stats_dict = {item['reaction_type']: item['count'] for item in reaction_stats}
        total_reactions = post.reactions.count()
        
        # Trả về một JSON Response với đầy đủ thông tin
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
        comment.save()

        # Render ra HTML cho comment mới
        comment_html = render_to_string('posts/_single_comment.html', {'comment': comment}, request=request)
        
        return JsonResponse({'status': 'ok', 'comment_html': comment_html})
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