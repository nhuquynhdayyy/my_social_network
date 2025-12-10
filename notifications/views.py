# notifications/views.py

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import truncatewords
from django.contrib.auth import get_user_model
from django.contrib import messages
from .models import Notification
from chat.models import Message
from posts.models import Comment, Post
from django.views.decorators.http import require_POST

User = get_user_model()

@login_required
def notification_list_view(request):
    # Bước 1: Lấy ID của các thông báo CHƯA ĐỌC trước khi thay đổi bất cứ điều gì.
    unread_ids = set(
        Notification.objects.filter(recipient=request.user, is_read=False).values_list('id', flat=True)
    )

    # Bước 2: Lấy toàn bộ danh sách thông báo để hiển thị.
    notifications = Notification.objects.filter(recipient=request.user).order_by('-timestamp') 

    # Bước 3: Bây giờ mới thực hiện việc đánh dấu là đã đọc.
    # Việc này không ảnh hưởng đến biến 'notifications' đã lấy ở trên.
    Notification.objects.filter(id__in=unread_ids).update(is_read=True)
    
    # Bước 4: Truyền cả danh sách thông báo và danh sách ID chưa đọc vào template.
    context = {
        'notifications': notifications,
        'unread_ids': unread_ids
    }
    return render(request, 'notifications/notification_list.html', context)

@login_required
def get_notifications(request):
    user = request.user
    notifications_data = []

    recent_notifications = Notification.objects.filter(
        recipient=user
    ).select_related('sender', 'target_content_type').order_by('-timestamp')[:15]

    total_unread = Notification.objects.filter(recipient=user, is_read=False).count()

    message_groups = {}
    other_notifications = []
    for n in recent_notifications:
        if n.notification_type == 'MESSAGE':
            if not n.target: continue
            conv_id = n.target.conversation_id
            if conv_id not in message_groups:
                message_groups[conv_id] = {'latest_notification': n, 'count': 0, 'is_read': n.is_read}
            message_groups[conv_id]['count'] += 1
            # Nếu có bất kỳ tin nhắn nào chưa đọc, cả nhóm được coi là chưa đọc
            if not n.is_read:
                message_groups[conv_id]['is_read'] = False
        else:
            other_notifications.append(n)

    for conv_id, group_data in message_groups.items():
        n = group_data['latest_notification']
        count = group_data['count']
        msg_obj = n.target
        msg_content_desc = "một tin nhắn mới."
        if msg_obj.file:
            if msg_obj.is_image: msg_content_desc = "một hình ảnh."
            elif msg_obj.is_video: msg_content_desc = "một video."
            else: msg_content_desc = "một tập tin."
       
        if count > 1:
            notif_text = f"đã gửi cho bạn {count} tin nhắn."
        else:
            notif_text = f"đã gửi cho bạn {msg_content_desc}"

        avatar = n.sender.avatar.url if n.sender.avatar else '/static/images/default.jpg'

        # notif_text = f"đã gửi cho bạn {count} tin nhắn mới." if count > 1 else "đã gửi cho bạn một tin nhắn mới."
        notifications_data.append({
            'id': n.id,
            'type': notif_text,
            'sender': n.sender.username,
            'avatar_url': avatar,
            'timestamp': timezone.localtime(n.timestamp).strftime('%H:%M %d-%m-%Y'),
            'link': reverse('notifications:redirect', args=[n.id]),
            'is_read': group_data['is_read'] 
        })

    for n in other_notifications:
        notif_text = ""
        target_content = ""
        if n.target and hasattr(n.target, 'content'):
            target_content = truncatewords(n.target.content, 7)
            
        if n.notification_type == 'FRIEND_REQUEST':
            notif_text = "đã gửi cho bạn một lời mời kết bạn."
        elif n.notification_type == 'FRIEND_ACCEPT': 
            notif_text = "đã chấp nhận lời mời kết bạn của bạn."
        elif n.notification_type == 'POST_REACTION':
            notif_text = f"đã bày tỏ cảm xúc về bài viết của bạn: \"{target_content}...\""
        elif n.notification_type == 'POST_COMMENT':
            notif_text = f"đã bình luận về bài viết của bạn: \"{target_content}...\""
        elif n.notification_type == 'COMMENT_REACTION':
            notif_text = f"đã bày tỏ cảm xúc về bình luận của bạn: \"{target_content}...\""
        elif n.notification_type == 'MESSAGE_REACTION': 
            notif_text = f"đã bày tỏ cảm xúc về tin nhắn của bạn: \"{target_content}...\""
        elif n.notification_type == 'POST_SHARE':
            # Nếu người chia sẻ có viết thêm caption (target_content)
            if target_content:
                notif_text = f"đã chia sẻ bài viết của bạn: \"{target_content}...\""
            else:
                notif_text = "đã chia sẻ bài viết của bạn."
        elif n.notification_type == 'ADDED_TO_GROUP':
            group_name = n.target.name if n.target else "Nhóm chưa đặt tên"
            notif_text = f"đã thêm bạn vào nhóm <strong>{group_name}</strong>."
        elif n.notification_type == 'GROUP_INVITE_REQUEST':
            group_name = n.target.name if n.target else "Nhóm chưa đặt tên"
            notif_text = f"muốn thêm thành viên vào nhóm <strong>{group_name}</strong>."
        
        avatar = n.sender.avatar.url if n.sender.avatar else '/static/images/default.jpg'

        notifications_data.append({
            'id': n.id,
            'type': notif_text,
            'sender': n.sender.username,
            'avatar_url': avatar,
            'timestamp': timezone.localtime(n.timestamp).strftime('%H:%M %d-%m-%Y'),
            'link': reverse('notifications:redirect', args=[n.id]),
            'is_read': n.is_read  
        })

    notifications_data.sort(key=lambda x: timezone.datetime.strptime(x['timestamp'], '%H:%M %d-%m-%Y'), reverse=True)

    return JsonResponse({
        'notifications': notifications_data,
        'total_unread': total_unread 
    })

@login_required
def redirect_notification(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    
    if notif.target is None:
        # 1. Xóa ngay thông báo "rác" này khỏi Database
        notif.delete()
        
        # 2. Báo cho người dùng biết (chỉ 1 lần này thôi)
        messages.warning(request, "Nội dung này đã bị xóa hoặc không còn tồn tại.")
        
        # 3. Quay về trang chủ
        return redirect("posts:home")
    
    # 1. Xử lý Tin nhắn
    if notif.notification_type == "MESSAGE" and notif.target:
        conv_id = notif.target.conversation_id
        message_ct = ContentType.objects.get_for_model(Message)
        message_ids_in_conv = Message.objects.filter(conversation_id=conv_id).values_list('id', flat=True)
        Notification.objects.filter(
            recipient=request.user,
            notification_type='MESSAGE',
            target_content_type=message_ct,
            target_object_id__in=message_ids_in_conv,
            is_read=False
        ).update(is_read=True)
        return redirect('chat:conversation_detail', conversation_id=conv_id)
    
    # 2. Đánh dấu đã đọc cho các loại thông báo khác
    else:
        notif.is_read = True
        notif.save()

    # 3. Xử lý chuyển hướng từng loại
    try:
        # === THÊM PHẦN NÀY: Xử lý Chia sẻ bài viết ===
        if notif.notification_type == "POST_SHARE" and notif.target:
            # notif.target chính là bài viết mới (bài chia sẻ)
            # Chuyển hướng thẳng đến trang chi tiết bài viết đó
            return redirect('posts:post_detail', pk=notif.target.id)
        # ============================================

        if notif.notification_type == "FRIEND_REQUEST":
            return redirect("accounts:friend_requests")

        if notif.notification_type == "FRIEND_ACCEPT" and notif.target:
            new_friend = notif.target 
            return redirect("accounts:profile", username=new_friend.username)
        
        # Sửa lại logic này một chút để ưu tiên trang chi tiết bài viết nếu có thể
        if notif.notification_type in ["POST_REACTION", "POST_COMMENT"] and notif.target:
            post = notif.target
            # Cách 1: Chuyển về trang cá nhân và cuộn tới bài viết 
            # profile_url = reverse("accounts:profile", kwargs={'username': post.author.username})
            # return redirect(f"{profile_url}#post-{post.id}")
            
            # Cách 2 (Khuyên dùng): Chuyển thẳng đến trang chi tiết bài viết
            return redirect('posts:post_detail', pk=post.id)

        if notif.notification_type == "COMMENT_REACTION" and notif.target:
            comment = notif.target
            post = comment.post
            return redirect('posts:post_detail', pk=post.id)
        
        if notif.notification_type == "MESSAGE_REACTION" and notif.target:
            message = notif.target
            return redirect("chat:conversation_detail", conversation_id=message.conversation_id)
        
        if notif.notification_type == 'ADDED_TO_GROUP' and notif.target:
            return redirect('chat:conversation_detail', conversation_id=notif.target.id)
    
        if notif.notification_type == 'GROUP_INVITE_REQUEST' and notif.target:
            return redirect('chat:manage_group', conversation_id=notif.target.id)

    except AttributeError:
        # Phòng trường hợp target bị xóa (ví dụ bài viết bị xóa)
        messages.warning(request, "Nội dung này không còn tồn tại.")

    # Mặc định về trang chủ
    return redirect("posts:home")

@login_required
def mark_all_as_read(request):
    # Cập nhật tất cả thông báo của user hiện tại thành đã đọc
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST # Chỉ chấp nhận lệnh POST (để bảo mật)
def delete_notification(request, notification_id):
    # 1. Tìm thông báo, đảm bảo nó tồn tại
    notification = get_object_or_404(Notification, id=notification_id)

    # 2. Kiểm tra chính chủ: Chỉ người nhận mới được quyền xóa
    if request.user == notification.recipient:
        notification.delete() # Xóa khỏi Database
        return JsonResponse({'status': 'success', 'message': 'Đã xóa thông báo'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền xóa'}, status=403)
    
@login_required
@require_POST
def mark_as_unread(request, notification_id):
    # 1. Tìm thông báo
    notification = get_object_or_404(Notification, id=notification_id)

    # 2. Kiểm tra chính chủ
    if request.user == notification.recipient:
        # 3. Đổi trạng thái thành CHƯA ĐỌC
        notification.is_read = False
        notification.save()
        return JsonResponse({'status': 'success', 'message': 'Đã đánh dấu là chưa đọc'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Không có quyền thao tác'}, status=403)