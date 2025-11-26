from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.contenttypes.models import ContentType
from django.template.defaultfilters import truncatewords

from .models import Notification
from chat.models import Message
from posts.models import Comment, Post

@login_required
def notification_list_view(request):
    notifications = Notification.objects.filter(recipient=request.user)
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return render(request, 'notifications/notification_list.html', {'notifications': notifications})

@login_required
def get_notifications(request):
    user = request.user
    notifications_data = []

    # 1. Lấy 15 thông báo gần đây nhất
    recent_notifications = Notification.objects.filter(
        recipient=user
    ).select_related('sender', 'target_content_type').order_by('-timestamp')[:15]

    # 2. Đếm riêng tổng số thông báo CHƯA ĐỌC
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
            if not n.is_read:
                message_groups[conv_id]['is_read'] = False
        else:
            other_notifications.append(n)

    for conv_id, group_data in message_groups.items():
        n = group_data['latest_notification']
        count = group_data['count']
        notif_text = f"đã gửi cho bạn {count} tin nhắn mới." if count > 1 else "đã gửi cho bạn một tin nhắn mới."
        notifications_data.append({
            'id': n.id,
            'type': notif_text,
            'sender': n.sender.username,
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
        elif n.notification_type == 'POST_REACTION':
            notif_text = f"đã bày tỏ cảm xúc về bài viết của bạn: \"{target_content}...\""
        elif n.notification_type == 'POST_COMMENT':
            notif_text = f"đã bình luận về bài viết của bạn: \"{target_content}...\""
        elif n.notification_type == 'COMMENT_REACTION':
            notif_text = f"đã bày tỏ cảm xúc về bình luận của bạn: \"{target_content}...\""
        # === XỬ LÝ THÔNG BÁO THÊM VÀO NHÓM ===
        elif n.notification_type == 'ADDED_TO_GROUP':
            group_name = "một nhóm chat"
            if n.target:
                group_name = n.target.name or "Nhóm chưa đặt tên"
            notif_text = f"đã thêm bạn vào nhóm <strong>{group_name}</strong>."
        elif n.notification_type == 'GROUP_INVITE_REQUEST':
            group_name = "một nhóm chat"
            if n.target: group_name = n.target.name or "Nhóm chưa đặt tên"
            notif_text = f"muốn thêm thành viên vào nhóm <strong>{group_name}</strong>."
        
        notifications_data.append({
            'id': n.id,
            'type': notif_text,
            'sender': n.sender.username,
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
    
    # Xử lý tin nhắn (Message)
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
    
    # Xử lý chung các loại khác: đánh dấu đã đọc
    notif.is_read = True
    notif.save()

    if notif.notification_type == "FRIEND_REQUEST":
        return redirect("accounts:friend_requests")

    if notif.notification_type in ["POST_REACTION", "POST_COMMENT"] and notif.target:
        post = notif.target
        profile_url = reverse("accounts:profile", kwargs={'username': post.author.username})
        return redirect(f"{profile_url}#post-{post.id}")

    if notif.notification_type == "COMMENT_REACTION" and notif.target:
        comment = notif.target
        post = comment.post
        profile_url = reverse("accounts:profile", kwargs={'username': post.author.username})
        return redirect(f"{profile_url}#post-{post.id}")
        
    # === CHUYỂN HƯỚNG KHI ĐƯỢC THÊM VÀO NHÓM ===
    if notif.notification_type == 'ADDED_TO_GROUP' and notif.target:
        return redirect('chat:conversation_detail', conversation_id=notif.target.id)
    
    if notif.notification_type == 'GROUP_INVITE_REQUEST' and notif.target:
        return redirect('chat:manage_group', conversation_id=notif.target.id)
        
    return redirect("home")