from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.db.models import OuterRef, Subquery, Count, Max
from django.contrib.contenttypes.models import ContentType

from .models import Notification
from chat.models import Message  # đảm bảo import đúng model Message

@login_required
def get_notifications(request):
    """
    Trả về JSON notifications đã được:
      - gộp các MESSAGE theo conversation và sender (kèm count, last_notif_id)
      - giữ các notification khác (friend request, post like/comment) riêng
    Response:
      {
        "notifications": [ {id, type, sender, count, timestamp, link, conversation_id}, ... ],
        "total_unread": <int>
      }
    """
    user = request.user
    notifications = []
    total_unread = 0

    # --- GROUP MESSAGE notifications ---
    message_ct = ContentType.objects.get_for_model(Message)

    # Lấy các notification MESSAGE chưa đọc của user và annotate conversation_id bằng Subquery
    msg_qs = Notification.objects.filter(
        recipient=user,
        is_read=False,
        notification_type='MESSAGE',
        target_content_type=message_ct
    ).annotate(
        conversation_id=Subquery(
            Message.objects.filter(pk=OuterRef('target_object_id')).values('conversation_id')[:1]
        )
    )

    # Group theo conversation_id và sender, lấy count và last timestamp + last notif id
    grouped = msg_qs.values('conversation_id', 'sender__username').annotate(
        count=Count('id'),
        last_ts=Max('timestamp'),
        last_notif_id=Max('id')
    ).order_by('-last_ts')

    for g in grouped:
        last_ts = g.get('last_ts')
        ts_local = timezone.localtime(last_ts).strftime('%H:%M %d-%m-%Y') if last_ts else ''
        last_notif_id = g.get('last_notif_id')
        notifications.append({
            'id': last_notif_id,
            'type': 'MESSAGE',
            'sender': g.get('sender__username'),
            'count': g.get('count'),
            'timestamp': ts_local,
            'link': reverse('notifications:redirect', args=[last_notif_id]),
            'conversation_id': g.get('conversation_id'),
            # sort key (ms) để sắp xếp sau
            '_sort_ts': last_ts.timestamp() if last_ts else 0
        })
        total_unread += g.get('count', 0)

    # --- OTHER notification types (each as one item) ---
    other_qs = Notification.objects.filter(recipient=user, is_read=False).exclude(notification_type='MESSAGE').order_by('-timestamp')
    for n in other_qs:
        ts_local = timezone.localtime(n.timestamp).strftime('%H:%M %d-%m-%Y')
        notifications.append({
            'id': n.id,
            'type': n.notification_type,
            'sender': n.sender.username if n.sender else None,
            'count': 1,
            'timestamp': ts_local,
            'link': reverse('notifications:redirect', args=[n.id]),
            '_sort_ts': n.timestamp.timestamp()
        })
        total_unread += 1

    # Sắp xếp chung theo thời gian giảm dần
    notifications.sort(key=lambda x: x.get('_sort_ts', 0), reverse=True)
    # Bỏ khóa sắp xếp trước khi trả về
    for item in notifications:
        item.pop('_sort_ts', None)

    return JsonResponse({'notifications': notifications, 'total_unread': total_unread})


@login_required
def redirect_notification(request, pk):
    """
    Khi user click notification:
     - nếu MESSAGE: đánh dấu tất cả notification MESSAGE cho same conversation -> is_read=True
       rồi redirect về conversation_detail
     - nếu FRIEND_REQUEST: mark this notif read và redirect về trang friend requests
     - nếu POST_LIKE/POST_COMMENT: mark and redirect về post detail
     - fallback: mark and redirect home
    """
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)

    # CASE: MESSAGE -> đánh dấu tất cả MESSAGE trong conversation
    if notif.notification_type == "MESSAGE" and notif.target:
        try:
            message = notif.target  # target là Message instance
            conv_id = message.conversation_id
        except Exception:
            # không lấy được conversation => mark this one và fallback
            notif.is_read = True
            notif.save()
            return redirect('home')

        # Lấy contenttype cho Message
        message_ct = ContentType.objects.get_for_model(Message)

        # Lấy tất cả message id thuộc conversation
        message_ids = Message.objects.filter(conversation_id=conv_id).values_list('id', flat=True)

        # Đánh dấu tất cả notification MESSAGE cho recipient + thuộc conversation này là đã đọc
        Notification.objects.filter(
            recipient=request.user,
            notification_type='MESSAGE',
            target_content_type=message_ct,
            target_object_id__in=message_ids,
            is_read=False
        ).update(is_read=True)

        return redirect('chat:conversation_detail', conversation_id=conv_id)

    # Các loại khác: mark này notif rồi redirect theo loại
    notif.is_read = True
    notif.save()

    if notif.notification_type == "FRIEND_REQUEST":
        return redirect("accounts:friend_requests")

    if notif.notification_type in ["POST_LIKE", "POST_COMMENT"] and notif.target:
        return redirect("posts:post_detail", pk=notif.target.id)

    return redirect("home")