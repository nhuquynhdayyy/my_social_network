# chat/views.py

from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, F
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
from .models import Conversation, Message
# SỬA Ở ĐÂY: Import cả hai form
from .forms import MessageForm, GroupCreationForm, RenameGroupForm, AddMembersForm, AdminSettingsForm
import json
from posts.models import Reaction
from django.urls import reverse
from django.contrib import messages

User = get_user_model()

@login_required
def manage_group_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, type='GROUP')
    
    if not conversation.participants.filter(pk=request.user.pk).exists():
        return HttpResponseForbidden("Bạn không phải là thành viên của nhóm này.")

    if request.method == 'POST':
        if 'toggle_admin_mode' in request.POST:
            if request.user != conversation.admin: return HttpResponseForbidden("Chỉ admin có quyền này.")
            form = AdminSettingsForm(request.POST, instance=conversation)
            if form.is_valid():
                form.save()
                messages.success(request, 'Đã cập nhật cài đặt nhóm.')
                return redirect('chat:manage_group', conversation_id=conversation.id)
        
        elif 'rename_group' in request.POST:
            if conversation.admin_only_management and request.user != conversation.admin:
                return HttpResponseForbidden("Chỉ admin có quyền đổi tên nhóm.")
            form = RenameGroupForm(request.POST, instance=conversation)
            if form.is_valid():
                form.save()
                messages.success(request, 'Đã đổi tên nhóm thành công.')
                return redirect('chat:manage_group', conversation_id=conversation.id)
        
        elif 'add_members' in request.POST:
            if conversation.admin_only_management and request.user != conversation.admin:
                return HttpResponseForbidden("Chỉ admin có quyền thêm thành viên.")
            form = AddMembersForm(request.POST, conversation=conversation)
            if form.is_valid():
                new_members = form.cleaned_data['new_members']
                conversation.participants.add(*new_members)
                messages.success(request, 'Đã thêm thành viên mới.')
                return redirect('chat:manage_group', conversation_id=conversation.id)

    context = {
        'conversation': conversation,
        'settings_form': AdminSettingsForm(instance=conversation),
        'rename_form': RenameGroupForm(instance=conversation),
        'add_members_form': AddMembersForm(conversation=conversation),
        'is_group_admin': request.user == conversation.admin,
    }
    return render(request, 'chat/manage_group.html', context)

# ------------------- VIEW MỚI ĐỂ TẠO NHÓM -------------------
@login_required
def create_group_view(request):
    if request.method == 'POST':
        # Truyền user hiện tại vào form để loại bỏ họ khỏi danh sách lựa chọn
        form = GroupCreationForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            group = form.save(commit=False)
            group.type = 'GROUP' # Đánh dấu đây là một nhóm chat
            group.admin = request.user # Người tạo là quản trị viên
            group.save() # Lưu lại để có ID

            # Lấy danh sách thành viên đã chọn từ form
            participants = form.cleaned_data['participants']
            # Thêm người tạo và các thành viên đã chọn vào nhóm
            group.participants.add(request.user, *participants)
            
            # Chuyển hướng đến phòng chat của nhóm vừa tạo
            return redirect('chat:conversation_detail', conversation_id=group.id)
    else:
        form = GroupCreationForm(user=request.user)
    return render(request, 'chat/create_group.html', {'form': form})


# ------------------- VIEW TRANG DANH SÁCH (Không thay đổi) -------------------
@login_required
def conversation_list_view(request):
    conversations = request.user.conversations.order_by('-updated_at')
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})


# ------------------- BẮT ĐẦU CONVERSATION (Cập nhật) -------------------
@login_required
def start_conversation_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if other_user == request.user:
        return redirect('chat:conversation_list')

    # Chỉ tìm trong các cuộc trò chuyện CÁ NHÂN đã có
    conversation = Conversation.objects.filter(
        type='PRIVATE', participants=request.user
    ).filter(participants=other_user).first()

    if not conversation:
        # Khi tạo mới, ghi rõ type là PRIVATE
        conversation = Conversation.objects.create(type='PRIVATE')
        conversation.participants.add(request.user, other_user)

    return redirect('chat:conversation_detail', conversation_id=conversation.id)


# ------------------- HIỂN THỊ CHI TIẾT (Cập nhật) -------------------
@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    other_participant = None
    # Chỉ lấy thông tin người còn lại nếu đây là chat cá nhân
    if conversation.type == 'PRIVATE':
        other_participant = conversation.participants.exclude(id=request.user.id).first()

    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            return redirect('chat:conversation_detail', conversation_id=conversation.id)

    messages = conversation.messages.select_related('sender').all()
    form = MessageForm()

    # Logic lấy reaction cho tin nhắn (giữ nguyên)
    message_ids = [msg.id for msg in messages]
    message_content_type = ContentType.objects.get_for_model(Message)
    user_reactions = Reaction.objects.filter(
        user=request.user,
        content_type=message_content_type,
        object_id__in=message_ids
    ).values('object_id', 'reaction_type')
    user_reactions_map = {item['object_id']: item['reaction_type'] for item in user_reactions}

    participants = conversation.participants.all().order_by('first_name')


    context = {
        'conversation': conversation,
        'messages': messages,
        'form': form,
        'other_participant': other_participant,
        'user_reactions_map': user_reactions_map,
        'is_group_admin': conversation.admin == request.user,
        'participants': participants # <-- Thêm dòng này
    }
    return render(request, 'chat/conversation_detail.html', context)


# ------------------- API GỬI TIN NHẮN (Không thay đổi) -------------------
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
            conversation.last_message = message
            conversation.updated_at = timezone.now()
            conversation.save()
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


# ------------------- API XÓA TIN NHẮN (Không thay đổi) -------------------
@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)
        if message.sender != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        message.delete()
        return JsonResponse({'status': 'ok', 'message_id': message_id})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


# ------------------- API SỬA TIN NHẮN (Không thay đổi) -------------------
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


# ------------------- API LẤY CONVERSATIONS (Cập nhật) -------------------
@login_required
def api_get_conversations(request):
    conversations = request.user.conversations.order_by('-updated_at')[:15]
    data = []
    for conv in conversations:
        conv_name = ''
        conv_avatar_url = ''

        # Logic để lấy đúng tên và ảnh đại diện
        if conv.type == 'GROUP':
            conv_name = conv.name
            conv_avatar_url = conv.avatar.url
        else: # PRIVATE
            other_participant = conv.participants.exclude(id=request.user.id).first()
            if not other_participant: continue
            conv_name = other_participant.username
            conv_avatar_url = other_participant.avatar.url
        
        last_message_text = ''
        if conv.last_message:
            # Logic để hiển thị đúng người gửi tin nhắn cuối
            if conv.last_message.sender == request.user:
                sender_prefix = "Bạn: "
            elif conv.type == 'GROUP':
                sender_prefix = f"{conv.last_message.sender.first_name}: "
            else:
                sender_prefix = ""
            last_message_text = f"{sender_prefix}{conv.last_message.text}"
        
        data.append({
            'conversation_id': conv.id,
            'name': conv_name,
            'avatar_url': conv_avatar_url,
            'last_message': last_message_text,
            'detail_url': reverse('chat:conversation_detail', kwargs={'conversation_id': conv.id})
        })
    return JsonResponse({'conversations': data})


# ------------------- API TÌM KIẾM USER (Không thay đổi) -------------------
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
        data.append({
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'start_conversation_url': reverse('chat:start_conversation', kwargs={'user_id': user.id})
        })
    return JsonResponse({'users': data})

# ------------------- API REACTION TIN NHẮN (Không thay đổi) -------------------
@login_required
def react_to_message_api(request, message_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
    message = get_object_or_404(Message, id=message_id)
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
    existing_reaction, created = Reaction.objects.get_or_create(
        user=request.user, content_type=content_type, object_id=message.id,
        defaults={'reaction_type': reaction_type}
    )
    current_user_reaction = reaction_type
    if not created:
        if existing_reaction.reaction_type == reaction_type:
            existing_reaction.delete()
            current_user_reaction = None
        else:
            existing_reaction.reaction_type = reaction_type
            existing_reaction.save()
    reaction_stats = message.reactions.values('reaction_type').annotate(count=Count('id'))
    stats_dict = {item['reaction_type']: item['count'] for item in reaction_stats}
    total_reactions = message.reactions.count()
    return JsonResponse({
        'status': 'ok',
        'total_reactions': total_reactions,
        'reaction_stats': stats_dict,
        'current_user_reaction': current_user_reaction
    })

# ------------------- API LẤY TIN NHẮN (Không thay đổi) -------------------
@login_required
def api_get_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    messages = conversation.messages.order_by('timestamp').annotate(
        author_id=F('sender_id')
    ).values('author_id', 'text', 'timestamp')
    messages_data = list(messages)
    return JsonResponse({'messages': messages_data})