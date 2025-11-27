from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Subquery, F
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
from .models import Conversation, Message
from .forms import MessageForm
import json
from posts.models import Reaction
from django.urls import reverse
from django.views.decorators.http import require_POST

User = get_user_model()


# ------------------- VIEW TRANG DANH SÁCH -------------------
@login_required
def conversation_list_view(request):
    conversations = request.user.conversations.order_by('-updated_at')
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})


# ------------------- BẮT ĐẦU CONVERSATION -------------------
@login_required
def start_conversation_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if other_user == request.user:
        return redirect('chat:conversation_list')

    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    return redirect('chat:conversation_detail', conversation_id=conversation.id)

# ------------------- CHI TIẾT CONVERSATION -------------------
@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_participant = conversation.participants.exclude(id=request.user.id).first()

    # Xử lý khi người dùng gửi tin nhắn mới
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            return redirect('chat:conversation_detail', conversation_id=conversation.id)

    # --- Logic chuẩn bị dữ liệu cho GET request ---
    messages = conversation.messages.exclude(hidden_by=request.user).order_by('timestamp')
    form = MessageForm()

    for message in messages:
        message.reaction_stats = message.reactions.values('reaction_type').annotate(count=Count('id'))

    message_ids = [msg.id for msg in messages]
    message_content_type = ContentType.objects.get_for_model(Message)
    user_reactions = Reaction.objects.filter(
        user=request.user,
        content_type=message_content_type,
        object_id__in=message_ids
    ).values('object_id', 'reaction_type')
    user_reactions_map = {item['object_id']: item['reaction_type'] for item in user_reactions}

    context = {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'other_participant': other_participant,
        'user_reactions_map': user_reactions_map
    }
    return render(request, 'chat/conversation_detail.html', context)

# ------------------- API GỬI TIN NHẮN (AJAX) -------------------
@login_required
def send_message_api(request, conversation_id):
    if request.method == 'POST':
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()

            # Cập nhật last_message
            conversation.last_message = message
            conversation.updated_at = timezone.now()
            conversation.save()

            # === Notification ===
            receivers = conversation.participants.exclude(id=request.user.id)
            ct = ContentType.objects.get_for_model(message)
            for receiver in receivers:
                Notification.objects.create(
                    recipient=receiver,
                    sender=request.user,
                    notification_type='MESSAGE',
                    target_content_type=ct,
                    target_object_id=message.id
                )

            local_ts = timezone.localtime(message.timestamp)
            formatted_ts = local_ts.strftime('%H:%M, %d-%m-%Y')

            return JsonResponse({
                'status': 'ok',
                'message_id': message.id,
                'sender': message.sender.username,
                'text': message.text,
                'timestamp': formatted_ts
            })
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


# ------------------- API XÓA TIN NHẮN -------------------
@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)

        # Lấy loại xóa từ request gửi lên ('me' hoặc 'everyone')
        # Lưu ý: request.body là dạng bytes, cần decode
        try:
            data = json.loads(request.body)
            delete_type = data.get('delete_type', 'me') # Mặc định là xóa phía tôi
        except:
            delete_type = 'me'

        # LOGIC XÓA
        if delete_type == 'everyone':
            # Chỉ người gửi mới được quyền xóa với mọi người
            if message.sender == request.user:
                message.delete()
                return JsonResponse({'status': 'ok', 'message_id': message_id, 'type': 'everyone'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Bạn không có quyền xóa tin nhắn này với mọi người.'}, status=403)
        
        elif delete_type == 'me':
            # Thêm user vào danh sách ẩn
            message.hidden_by.add(request.user)
            return JsonResponse({'status': 'ok', 'message_id': message_id, 'type': 'me'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


# ------------------- API SỬA TIN NHẮN -------------------
@login_required
def edit_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)

        if message.sender != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

        try:
            data = json.loads(request.body)
            new_text = data.get('text', '')
            if new_text:
                message.text = new_text
                message.save()

                return JsonResponse({
                    'status': 'ok',
                    'message_id': message_id,
                    'new_text': new_text
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Text cannot be empty'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


# ------------------- API LẤY CONVERSATIONS -------------------
@login_required
def api_get_conversations(request):
    conversations = request.user.conversations.order_by('-updated_at')[:10]

    data = []
    for conv in conversations:
        other_participant = conv.participants.exclude(id=request.user.id).first()
        if not other_participant:
            continue

        last_message_text = ''
        last_message_ts = None
        if conv.last_message:
            sender_prefix = "Bạn: " if conv.last_message.sender == request.user else ""
            last_message_text = f"{sender_prefix}{conv.last_message.text}"
            last_message_ts = timezone.localtime(conv.last_message.timestamp).strftime('%H:%M, %d-%m-%Y')

        data.append({
            'conversation_id': conv.id,
            'other_participant': {
                'username': other_participant.username,
                'avatar_url': other_participant.avatar.url if other_participant.avatar else None,
            },
            'last_message': last_message_text,
            'last_message_timestamp': last_message_ts,
            # SỬA DÒNG NÀY: Dùng `reverse` để tạo URL động và chính xác
            'detail_url': reverse('chat:conversation_detail', kwargs={'conversation_id': conv.id})
        })

    return JsonResponse({'conversations': data})


# ------------------- API TÌM KIẾM USER -------------------
@login_required
def api_search_users(request):
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    data = []
    for user in users:
        # --- SỬA ĐOẠN NÀY ---
        # Kiểm tra xem user có avatar không để lấy URL, nếu không thì trả về None
        avatar_url = None
        try:
            if user.avatar:
                avatar_url = user.avatar.url
        except ValueError:
            # Phòng trường hợp trường avatar tồn tại nhưng không có file
            pass

        data.append({
            'id': user.id, # Thêm ID để Javascript sử dụng
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'avatar_url': avatar_url, # <--- Bổ sung dòng này
            'start_conversation_url': f'/chat/start/{user.id}/'
        })
        # --------------------

    return JsonResponse({'users': data})

@login_required
def react_to_message_api(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

    message = get_object_or_404(Message, id=message_id)
    # Kiểm tra xem user có trong cuộc trò chuyện này không để đảm bảo quyền
    if not message.conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
        reaction_type = data.get('reaction_type')
        if not reaction_type:
            return JsonResponse({'status': 'error', 'message': 'Reaction type is required'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    content_type = ContentType.objects.get_for_model(Message)
    existing_reaction = Reaction.objects.filter(
        user=request.user, content_type=content_type, object_id=message.id
    ).first()

    current_user_reaction = None
    if existing_reaction:
        if existing_reaction.reaction_type == reaction_type:
            existing_reaction.delete() # Bỏ react
            current_user_reaction = None
        else:
            existing_reaction.reaction_type = reaction_type
            existing_reaction.save() # Thay đổi reaction
            current_user_reaction = reaction_type
    else:
        Reaction.objects.create(
            user=request.user,
            content_type=content_type,
            object_id=message.id,
            reaction_type=reaction_type
        ) # React mới
        current_user_reaction = reaction_type
        if request.user != message.sender:
            Notification.objects.create(
                recipient=message.sender, sender=request.user, notification_type='MESSAGE_REACTION',
                target_content_type=content_type, target_object_id=message.id
            )
            
    # Lấy lại thống kê reaction cho tin nhắn này
    reaction_stats = message.reactions.values('reaction_type').annotate(count=Count('id'))
    stats_dict = {item['reaction_type']: item['count'] for item in reaction_stats}
    total_reactions = message.reactions.count()
    
    return JsonResponse({
        'status': 'ok',
        'total_reactions': total_reactions,
        'reaction_stats': stats_dict,
        'current_user_reaction': current_user_reaction
    })

@login_required
def api_get_messages(request, conversation_id):
    # Đảm bảo người dùng hiện tại là một phần của cuộc hội thoại này để bảo mật
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # 1. Truy vấn đúng trường 'sender_id'.
    # 2. Dùng annotate() để đổi tên 'sender_id' thành 'author_id' ngay trong câu lệnh query.
    #    Đây là cách hiệu quả nhất.
    messages = conversation.messages.exclude(hidden_by=request.user).order_by('timestamp').annotate(
        author_id=F('sender_id')
    ).values('author_id', 'text', 'timestamp')
    
    # Chuyển QuerySet thành list of dicts
    messages_data = list(messages)
    
    return JsonResponse({'messages': messages_data})

@require_POST
@login_required
def api_start_conversation(request):
    try:
        data = json.loads(request.body)
        target_user_id = data.get('target_user_id')
        target_user = User.objects.get(id=target_user_id)
        
        # Tìm cuộc hội thoại cũ
        conversation = Conversation.objects.filter(participants=request.user).filter(participants=target_user).first()
        
        # Nếu chưa có thì tạo mới
        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, target_user)
            
        return JsonResponse({
            'status': 'ok', 
            'conversation_id': conversation.id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)