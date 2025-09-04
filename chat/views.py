# chat/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth import get_user_model
from .models import Conversation, Message
from .forms import MessageForm
from django.db.models import OuterRef, Subquery, F

import json

User = get_user_model()

@login_required
def conversation_list_view(request):
    # Lấy tất cả các cuộc hội thoại mà người dùng hiện tại tham gia
    # Sắp xếp theo thời gian cập nhật gần nhất
    conversations = request.user.conversations.order_by('-updated_at')
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})


@login_required
def start_conversation_view(request, user_id):
    # Tìm người dùng mục tiêu
    other_user = get_object_or_404(User, id=user_id)

    # Không cho phép tự chat với chính mình
    if other_user == request.user:
        return redirect('chat:conversation_list')

    # Tìm kiếm cuộc hội thoại đã tồn tại giữa 2 người
    # Dùng Q object để query participants
    conversation = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()

    # Nếu chưa có, tạo mới
    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    return redirect('chat:conversation_detail', conversation_id=conversation.id)


@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    messages = conversation.messages.all()
    form = MessageForm()
    
    # Lấy người tham gia còn lại trong cuộc trò chuyện
    other_participant = conversation.participants.exclude(id=request.user.id).first()

    context = {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'other_participant': other_participant
    }
    return render(request, 'chat/conversation_detail.html', context)


# --- API Views (dành cho JavaScript) ---

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
            
            # Cập nhật thời gian và tin nhắn cuối cùng của conversation
            conversation.last_message = message
            conversation.save()

            return JsonResponse({
                'status': 'ok',
                'message_id': message.id,
                'sender': message.sender.username,
                'text': message.text,
                'timestamp': message.timestamp.strftime('%H:%M, %d-%m-%Y')
            })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST': # Dùng POST để đơn giản hóa phía client
        message = get_object_or_404(Message, id=message_id)

        # Chỉ người gửi mới có quyền xóa
        if message.sender != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
        message.delete()
        return JsonResponse({'status': 'ok', 'message_id': message_id})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@login_required
def edit_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)

        # Chỉ người gửi mới có quyền sửa
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
@login_required
def api_get_conversations(request):
    """
    API endpoint để lấy danh sách các cuộc hội thoại gần đây.
    """
    # Lấy 10 cuộc hội thoại được cập nhật gần nhất
    conversations = request.user.conversations.order_by('-updated_at')[:10]
    
    data = []
    for conv in conversations:
        # Lấy người tham gia còn lại trong cuộc trò chuyện
        other_participant = conv.participants.exclude(id=request.user.id).first()
        if not other_participant:
            continue

        last_message_text = ''
        if conv.last_message:
            sender_prefix = "Bạn: " if conv.last_message.sender == request.user else ""
            last_message_text = f"{sender_prefix}{conv.last_message.text}"

        data.append({
            'conversation_id': conv.id,
            'other_participant': {
                'username': other_participant.username,
                # Giả sử bạn có model Profile liên kết với User để lấy avatar
                # 'avatar_url': other_participant.profile.avatar.url 
            },
            'last_message': last_message_text,
            'detail_url': f'/chat/{conv.id}/' # URL để chuyển đến khi click
        })

    return JsonResponse({'conversations': data})
@login_required
def api_search_users(request):
    """
    API endpoint để tìm kiếm người dùng theo username hoặc first/last name.
    """
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'users': []})

    # Tìm kiếm người dùng, loại trừ chính mình, giới hạn 10 kết quả
    users = User.objects.filter(
        Q(username__icontains=query) | 
        Q(first_name__icontains=query) | 
        Q(last_name__icontains=query)
    ).exclude(id=request.user.id)[:10]

    data = []
    for user in users:
        data.append({
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            # URL để bắt đầu cuộc trò chuyện
            'start_conversation_url': f'/chat/start/{user.id}/'
        })

    return JsonResponse({'users': data})