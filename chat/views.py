from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
from .models import Conversation, Message, GroupMembershipRequest
from .forms import MessageForm, GroupCreationForm, GroupUpdateForm, AddMembersForm, AdminSettingsForm
import json
from posts.models import Reaction
from django.urls import reverse
from django.contrib import messages

User = get_user_model()

# ============================================================================
# 1. CÁC VIEW QUẢN LÝ NHÓM (LOGIC BACKEND)
# ============================================================================

@login_required
def manage_group_view(request, conversation_id):
    """
    Xử lý các hành động quản lý nhóm (Đổi tên, Cài đặt Admin, Thêm thành viên, Xóa nhóm).
    Sau khi xử lý xong sẽ redirect về trang Chat (conversation_detail).
    """
    conversation = get_object_or_404(Conversation, id=conversation_id, type='GROUP')
    
    # Kiểm tra thành viên
    if not conversation.participants.filter(pk=request.user.pk).exists():
        return HttpResponseForbidden("Bạn không phải là thành viên của nhóm này.")

    is_admin = (request.user == conversation.admin)

    if request.method == 'POST':
        # --- A. XÓA NHÓM VĨNH VIỄN ---
        if 'delete_group' in request.POST:
            if not is_admin:
                messages.error(request, "Chỉ Admin mới có quyền xóa nhóm.")
            else:
                group_name = conversation.name
                conversation.delete()
                messages.success(request, f"Đã xóa nhóm '{group_name}' thành công.")
                return redirect('chat:conversation_list')

        # --- B. CÀI ĐẶT ADMIN (TOGGLE CHẾ ĐỘ KIỂM DUYỆT) ---
        elif 'toggle_admin_mode' in request.POST:
            if not is_admin:
                messages.error(request, "Chỉ Admin mới có quyền thay đổi cài đặt này.")
            else:
                form = AdminSettingsForm(request.POST, instance=conversation)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Đã cập nhật cài đặt nhóm.')
        
        # --- C. CẬP NHẬT THÔNG TIN (TÊN, AVATAR) ---
        elif 'update_group_info' in request.POST:
            if conversation.admin_only_management and not is_admin:
                messages.error(request, "Nhóm đang bật chế độ chỉ Admin được thay đổi thông tin.")
            else:
                form = GroupUpdateForm(request.POST, request.FILES, instance=conversation)
                if form.is_valid():
                    conversation = form.save()
                    changes = []
                    if 'name' in form.changed_data: changes.append(f"đổi tên nhóm thành '{conversation.name}'")
                    if 'avatar' in form.changed_data: changes.append("đổi ảnh đại diện nhóm")
                    
                    if changes:
                        msg_text = f"{request.user.get_full_name()} đã " + " và ".join(changes) + "."
                        Message.objects.create(conversation=conversation, sender=None, text=msg_text)
                    messages.success(request, 'Đã cập nhật thông tin nhóm.')
        
        # --- D. THÊM THÀNH VIÊN ---
        elif 'add_members' in request.POST:
            form = AddMembersForm(request.POST, conversation=conversation)
            if form.is_valid():
                new_members = form.cleaned_data['new_members']
                
                # TH 1: Cần duyệt (User thường + Chế độ admin on)
                if conversation.admin_only_management and not is_admin:
                    conv_content_type = ContentType.objects.get_for_model(Conversation)
                    for member in new_members:
                        # Kiểm tra xem đã có request chưa để tránh duplicate
                        if not GroupMembershipRequest.objects.filter(conversation=conversation, user_to_add=member).exists():
                            GroupMembershipRequest.objects.create(conversation=conversation, invited_by=request.user, user_to_add=member)
                            Notification.objects.create(
                                recipient=conversation.admin, sender=request.user, notification_type='GROUP_INVITE_REQUEST',
                                target_content_type=conv_content_type, target_object_id=conversation.id
                            )
                    messages.info(request, f"Đã gửi yêu cầu thêm {new_members.count()} thành viên. Chờ Admin phê duyệt.")
                
                # TH 2: Thêm trực tiếp
                else:
                    conversation.participants.add(*new_members)
                    names = ", ".join([u.get_full_name() or u.username for u in new_members])
                    Message.objects.create(conversation=conversation, sender=None, text=f"{request.user.get_full_name()} đã thêm {names} vào nhóm.")
                    
                    conv_content_type = ContentType.objects.get_for_model(Conversation)
                    for member in new_members:
                        Notification.objects.create(
                            recipient=member, sender=request.user, notification_type='ADDED_TO_GROUP',
                            target_content_type=conv_content_type, target_object_id=conversation.id
                        )
                    messages.success(request, 'Đã thêm thành viên mới.')

    # Redirect về trang chat chi tiết để thấy thay đổi ngay lập tức
    return redirect('chat:conversation_detail', conversation_id=conversation.id)


@login_required
def handle_membership_request(request, request_id, action):
    req = get_object_or_404(GroupMembershipRequest, id=request_id)
    conversation = req.conversation
    
    if request.user != conversation.admin:
        messages.error(request, "Bạn không có quyền thực hiện hành động này.")
        return redirect('chat:conversation_detail', conversation_id=conversation.id)

    if action == 'approve':
        conversation.participants.add(req.user_to_add)
        Message.objects.create(conversation=conversation, sender=None, text=f"Admin đã duyệt yêu cầu thêm {req.user_to_add.get_full_name()} vào nhóm.")
        Notification.objects.create(
            recipient=req.user_to_add, sender=request.user, notification_type='ADDED_TO_GROUP',
            target_content_type=ContentType.objects.get_for_model(Conversation), target_object_id=conversation.id
        )
        req.delete()
        messages.success(request, f"Đã thêm {req.user_to_add.username} vào nhóm.")
    elif action == 'reject':
        req.delete()
        messages.info(request, f"Đã từ chối yêu cầu thêm {req.user_to_add.username}.")

    return redirect('chat:conversation_detail', conversation_id=conversation.id)


@login_required
def leave_group_view(request, conversation_id):
    if request.method == 'POST':
        conversation = get_object_or_404(Conversation, id=conversation_id, type='GROUP')
        if not conversation.participants.filter(pk=request.user.pk).exists():
            return HttpResponseForbidden("Bạn không phải là thành viên của nhóm này.")
            
        user_who_left = request.user
        Message.objects.create(conversation=conversation, sender=None, text=f"{user_who_left.get_full_name()} đã rời khỏi nhóm.")

        if user_who_left == conversation.admin:
            conversation.participants.remove(user_who_left)
            remaining_members = conversation.participants.all()
            if remaining_members.exists():
                new_admin = remaining_members.order_by('pk').first()
                conversation.admin = new_admin
                conversation.save()
                messages.info(request, f"Bạn đã rời nhóm. {new_admin.username} là admin mới.")
            else:
                conversation.delete()
                messages.success(request, "Nhóm đã giải tán.")
                return redirect('chat:conversation_list')
        else:
            conversation.participants.remove(user_who_left)
            messages.success(request, f"Bạn đã rời khỏi nhóm {conversation.name}.")
        
        return redirect('chat:conversation_list')
    return redirect('posts:home')


@login_required
def create_group_view(request):
    initial_data = {}
    pre_selected_user_id = request.GET.get('with_user')
    if pre_selected_user_id:
        try:
            target_user = User.objects.get(pk=pre_selected_user_id)
            initial_data['participants'] = [target_user.pk]
        except User.DoesNotExist:
            pass

    if request.method == 'POST':
        form = GroupCreationForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            group = form.save(commit=False)
            group.type = 'GROUP'
            group.admin = request.user
            group.save()
            participants = form.cleaned_data['participants']
            group.participants.add(request.user, *participants)
            
            Message.objects.create(conversation=group, sender=None, text=f"{request.user.get_full_name()} đã tạo nhóm '{group.name}'." )
            
            conv_content_type = ContentType.objects.get_for_model(Conversation)
            for member in participants:
                 Notification.objects.create(
                    recipient=member, sender=request.user, notification_type='ADDED_TO_GROUP',
                    target_content_type=conv_content_type, target_object_id=group.id
                )
            return redirect('chat:conversation_detail', conversation_id=group.id)
    else:
        form = GroupCreationForm(user=request.user, initial=initial_data)
        
    return render(request, 'chat/create_group.html', {'form': form})


@login_required
def remove_member(request, conversation_id, user_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, type='GROUP')
    member_to_remove = get_object_or_404(User, id=user_id)
    
    if not conversation.participants.filter(pk=request.user.pk).exists():
        messages.error(request, "Bạn không phải là thành viên của nhóm này.")
        return redirect('chat:conversation_detail', conversation_id=conversation.id)

    if request.user == member_to_remove:
        messages.warning(request, "Vui lòng dùng nút 'Rời khỏi nhóm'.")
        return redirect('chat:conversation_detail', conversation_id=conversation.id)

    if member_to_remove == conversation.admin:
        messages.error(request, "Không thể xóa Quản trị viên khỏi nhóm.")
        return redirect('chat:conversation_detail', conversation_id=conversation.id)

    is_admin = (request.user == conversation.admin)
    if conversation.admin_only_management and not is_admin:
        messages.error(request, "Nhóm đang bật chế độ Quản trị viên. Bạn không có quyền xóa thành viên.")
        return redirect('chat:conversation_detail', conversation_id=conversation.id)
    
    conversation.participants.remove(member_to_remove)
    Message.objects.create(conversation=conversation, sender=None, text=f"{request.user.get_full_name()} đã xóa {member_to_remove.get_full_name()} khỏi nhóm.")
    messages.success(request, f"Đã mời {member_to_remove.username} ra khỏi nhóm.")
    return redirect('chat:conversation_detail', conversation_id=conversation.id)


@login_required
def conversation_list_view(request):
    conversations = request.user.conversations.order_by('-updated_at')
    return render(request, 'chat/conversation_list.html', {'conversations': conversations})


@login_required
def start_conversation_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return redirect('chat:conversation_list')
    conversation = Conversation.objects.filter(type='PRIVATE', participants=request.user).filter(participants=other_user).first()
    if not conversation:
        conversation = Conversation.objects.create(type='PRIVATE')
        conversation.participants.add(request.user, other_user)
    return redirect('chat:conversation_detail', conversation_id=conversation.id)


# ============================================================================
# 2. VIEW CHI TIẾT CHAT (QUAN TRỌNG: GỬI KÈM FORM CHO SIDEBAR)
# ============================================================================
@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_participant = None
    if conversation.type == 'PRIVATE':
        other_participant = conversation.participants.exclude(id=request.user.id).first()

    # Xử lý gửi tin nhắn (Dự phòng nếu JS bị tắt)
    if request.method == "POST" and 'text' in request.POST:
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            conversation.last_message = message
            conversation.updated_at = timezone.now()
            conversation.save()
            return redirect('chat:conversation_detail', conversation_id=conversation.id)

    messages_qs = conversation.messages.select_related('sender').all()
    form = MessageForm()
    
    # Lấy Reaction của user để hiển thị nút đã like/chưa like
    message_ids = [msg.id for msg in messages_qs]
    message_content_type = ContentType.objects.get_for_model(Message)
    user_reactions = Reaction.objects.filter(
        user=request.user, content_type=message_content_type, object_id__in=message_ids
    ).values('object_id', 'reaction_type')
    user_reactions_map = {item['object_id']: item['reaction_type'] for item in user_reactions}

    participants = conversation.participants.all().order_by('first_name')

    # Context cơ bản
    context = {
        'conversation': conversation,
        'messages': messages_qs,
        'form': form,
        'other_participant': other_participant,
        'user_reactions_map': user_reactions_map,
        'is_group_admin': (conversation.admin == request.user),
        'participants': participants,
    }

    # === QUAN TRỌNG: GỬI KÈM FORM QUẢN LÝ NHÓM VÀO CONTEXT (ĐỂ HIỂN THỊ Ở SIDEBAR) ===
    if conversation.type == 'GROUP':
        context['update_info_form'] = GroupUpdateForm(instance=conversation)
        context['add_members_form'] = AddMembersForm(conversation=conversation)
        context['settings_form'] = AdminSettingsForm(instance=conversation)
        # Nếu là admin thì lấy danh sách yêu cầu chờ duyệt
        if conversation.admin == request.user:
             context['pending_requests'] = conversation.membership_requests.select_related('invited_by', 'user_to_add').all()

    return render(request, 'chat/conversation_detail.html', context)


# ============================================================================
# 3. CÁC API VIEWS (ĐẦY ĐỦ KHÔNG RÚT GỌN)
# ============================================================================

@login_required
def send_message_api(request, conversation_id):
    if request.method == 'POST':
        conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
        form = MessageForm(request.POST, request.FILES)
        
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            
            if not message.text and not message.file:
                 return JsonResponse({'status': 'error', 'message': 'Tin nhắn rỗng'}, status=400)

            message.save()
            conversation.last_message = message
            conversation.updated_at = timezone.now()
            conversation.save()
            
            # Gửi thông báo
            receivers = conversation.participants.exclude(id=request.user.id)
            ct = ContentType.objects.get_for_model(message)
            for receiver in receivers:
                Notification.objects.create(
                    recipient=receiver, sender=request.user, notification_type='MESSAGE',
                    target_content_type=ct, target_object_id=message.id
                )
            
            local_ts = timezone.localtime(message.timestamp)
            formatted_ts = local_ts.strftime('%H:%M, %d-%m-%Y')
            
            file_url = message.file.url if message.file else None
            file_type = 'file'
            if message.file:
                if message.is_image: file_type = 'image'
                elif message.is_video: file_type = 'video'

            return JsonResponse({
                'status': 'ok', 'message_id': message.id, 'sender': message.sender.username,
                'text': message.text, 'timestamp': formatted_ts, 'file_url': file_url, 'file_type': file_type
            })
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)
        if message.sender != request.user:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        message.delete()
        return JsonResponse({'status': 'ok', 'message_id': message_id})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

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
                return JsonResponse({'status': 'ok', 'message_id': message_id, 'new_text': new_text})
            else:
                return JsonResponse({'status': 'error', 'message': 'Text cannot be empty'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@login_required
def api_get_conversations(request):
    conversations = request.user.conversations.order_by('-updated_at')[:15]
    data = []
    for conv in conversations:
        conv_name = ''
        conv_avatar_url = ''
        if conv.type == 'GROUP':
            conv_name = conv.name
            conv_avatar_url = conv.avatar.url
        else:
            other_participant = conv.participants.exclude(id=request.user.id).first()
            if not other_participant: continue
            conv_name = other_participant.username
            conv_avatar_url = other_participant.avatar.url
        
        last_message_text = ''
        if conv.last_message:
            sender_prefix = ""
            if conv.last_message.sender == request.user: sender_prefix = "Bạn: "
            elif conv.type == 'GROUP' and conv.last_message.sender: sender_prefix = f"{conv.last_message.sender.first_name}: "
            
            content = conv.last_message.text
            if conv.last_message.file:
                if conv.last_message.is_image: content = "[Hình ảnh]"
                elif conv.last_message.is_video: content = "[Video]"
                else: content = "[File]"
            last_message_text = f"{sender_prefix}{content}"
        
        data.append({
            'conversation_id': conv.id, 'name': conv_name, 'avatar_url': conv_avatar_url,
            'last_message': last_message_text,
            'detail_url': reverse('chat:conversation_detail', kwargs={'conversation_id': conv.id})
        })
    return JsonResponse({'conversations': data})

@login_required
def api_get_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    messages = conversation.messages.order_by('timestamp')
    messages_data = []
    for msg in messages:
        file_url = msg.file.url if msg.file else None
        file_type = None
        if msg.file:
            if msg.is_image: file_type = 'image'
            elif msg.is_video: file_type = 'video'
            else: file_type = 'file'
        messages_data.append({
            'author_id': msg.sender_id if msg.sender else None, 'text': msg.text,
            'timestamp': timezone.localtime(msg.timestamp).strftime('%H:%M, %d-%m-%Y'),
            'file_url': file_url, 'file_type': file_type
        })
    return JsonResponse({'messages': messages_data})

@login_required
def api_search_users(request):
    query = request.GET.get('q', '').strip()
    if not query: return JsonResponse({'users': []})
    users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query)).exclude(id=request.user.id)[:10]
    data = []
    for user in users:
        data.append({
            'username': user.username, 'full_name': user.get_full_name() or user.username,
            'start_conversation_url': reverse('chat:start_conversation', kwargs={'user_id': user.id})
        })
    return JsonResponse({'users': data})

@login_required
def react_to_message_api(request, message_id):
    if request.method != 'POST': return JsonResponse({'status': 'error'}, status=400)
    message = get_object_or_404(Message, id=message_id)
    if not message.conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'status': 'error'}, status=403)
    try:
        data = json.loads(request.body)
        reaction_type = data.get('reaction_type')
        if not reaction_type: return JsonResponse({'status': 'error'}, status=400)
    except: return JsonResponse({'status': 'error'}, status=400)
    
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
        'status': 'ok', 'total_reactions': total_reactions,
        'reaction_stats': stats_dict, 'current_user_reaction': current_user_reaction
    })