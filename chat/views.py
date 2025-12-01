from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Subquery, F
from django.contrib.contenttypes.models import ContentType
from notifications.models import Notification
from .models import Conversation, Message, GroupMembershipRequest
from .forms import MessageForm, GroupCreationForm, GroupUpdateForm, AddMembersForm, AdminSettingsForm
import json
from posts.models import Reaction
from django.urls import reverse
from django.views.decorators.http import require_POST
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
    # View này bây giờ chủ yếu xử lý POST từ Modal
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
            messages.success(request, "Tạo nhóm thành công!")
            return redirect('chat:conversation_detail', conversation_id=group.id)
        else:
            # Nếu lỗi form, quay lại trang danh sách và báo lỗi
            messages.error(request, "Tạo nhóm thất bại. Vui lòng kiểm tra lại thông tin (thêm ít nhất 2 thành viên).")
            return redirect('chat:conversation_list')
    else:
        # Nếu truy cập GET trực tiếp, redirect về list
        return redirect('chat:conversation_list')


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
# ============================================================================

# ------------------- VIEW TRANG DANH SÁCH -------------------
@login_required
def conversation_list_view(request):
    conversations = request.user.conversations.order_by('-updated_at')
    group_creation_form = GroupCreationForm(user=request.user)
    return render(request, 'chat/conversation_list.html', {
        'conversations': conversations,
        'group_creation_form': group_creation_form
    })


# ------------------- BẮT ĐẦU CONVERSATION -------------------
@login_required
def start_conversation_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    if other_user == request.user:
        return redirect('chat:conversation_list')

    conversation = Conversation.objects.filter(
        type='PRIVATE', participants=request.user
    ).filter(
        participants=other_user
    ).first()

    if not conversation:
        conversation = Conversation.objects.create(type='PRIVATE')
        conversation.participants.add(request.user, other_user)

    return redirect('chat:conversation_detail', conversation_id=conversation.id)

# ------------------- CHI TIẾT CONVERSATION -------------------
@login_required
def conversation_detail_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_participant = None
    if conversation.type == 'PRIVATE':
        other_participant = conversation.participants.exclude(id=request.user.id).first()

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

    participants = conversation.participants.all().order_by('first_name')

    context = {
        'conversation': conversation,
        'chat_messages': messages,
        'form': form,
        'other_participant': other_participant,
        'user_reactions_map': user_reactions_map,
        'is_group_admin': (conversation.admin == request.user),
        'participants': participants,
        'group_creation_form': GroupCreationForm(user=request.user) 
    }

    if conversation.type == 'GROUP':
        context['update_info_form'] = GroupUpdateForm(instance=conversation)
        context['add_members_form'] = AddMembersForm(conversation=conversation)
        context['settings_form'] = AdminSettingsForm(instance=conversation)
        if conversation.admin == request.user:
             context['pending_requests'] = conversation.membership_requests.select_related('invited_by', 'user_to_add').all()

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
            if not message.text and not message.file:
                 return JsonResponse({'status': 'error', 'message': 'Tin nhắn rỗng'}, status=400)
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

            file_url = message.file.url if message.file else None
            file_type = 'file'
            if message.file:
                if message.is_image: file_type = 'image'
                elif message.is_video: file_type = 'video'

            return JsonResponse({
                'status': 'ok',
                'message_id': message.id,
                'sender': message.sender.username,
                'text': message.text,
                'timestamp': formatted_ts,
                'file_url': file_url,
                'file_type': file_type
            })
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


# ------------------- API XÓA TIN NHẮN -------------------
@login_required
def delete_message_api(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id)

        # Kiểm tra bảo mật: Người xóa phải là thành viên trong cuộc trò chuyện
        if request.user not in message.conversation.participants.all():
             return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

        try:
            data = json.loads(request.body)
            delete_type = data.get('delete_type', 'me')
        except:
            delete_type = 'me'

        # LOGIC XÓA
        if delete_type == 'everyone':
            # CHỈ NGƯỜI GỬI mới được thu hồi
            if message.sender == request.user:
                message.delete()
                return JsonResponse({'status': 'ok', 'message_id': message_id, 'type': 'everyone'})
            else:
                return JsonResponse({'status': 'error', 'message': 'Bạn không thể thu hồi tin nhắn của người khác.'}, status=403)
        
        elif delete_type == 'me':
            # AI CŨNG ĐƯỢC QUYỀN XÓA PHÍA MÌNH (Kể cả không phải người gửi)
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
    try:
        conversations = request.user.conversations.order_by('-updated_at')[:15]
        data = []
        for conv in conversations:
            conv_name = ''
            conv_avatar_url = ''
            
            # --- XỬ LÝ AVATAR AN TOÀN ---
            try:
                if conv.type == 'GROUP':
                    conv_name = conv.name
                    if conv.avatar:
                        conv_avatar_url = conv.avatar.url
                    else:
                        conv_avatar_url = '/static/images/group_default.png' # Ảnh mặc định nếu thiếu
                else:
                    other_participant = conv.participants.exclude(id=request.user.id).first()
                    if not other_participant: 
                        continue
                    
                    conv_name = other_participant.username
                    # Kiểm tra kỹ avatar của user
                    if other_participant.avatar:
                        conv_avatar_url = other_participant.avatar.url
                    else:
                        conv_avatar_url = '/static/images/default_avatar.png' # Ảnh mặc định
            except ValueError:
                # Nếu file ảnh bị lỗi đường dẫn, dùng ảnh mặc định để tránh sập API
                conv_avatar_url = '/static/images/default_avatar.png' 
            # ---------------------------

            last_message_ts = None
            last_message_text = ''
            if conv.last_message:
                sender_prefix = ""
                if conv.last_message.sender == request.user: 
                    sender_prefix = "Bạn: "
                elif conv.type == 'GROUP' and conv.last_message.sender: 
                    sender_prefix = f"{conv.last_message.sender.first_name}: "
                
                content = conv.last_message.text
                if conv.last_message.file:
                    if conv.last_message.is_image: content = "[Hình ảnh]"
                    elif conv.last_message.is_video: content = "[Video]"
                    else: content = "[File]"
                    
                # Xử lý trường hợp text là None nhưng có file
                if content is None:
                    content = ""
                    
                last_message_text = f"{sender_prefix}{content}"
                last_message_ts = timezone.localtime(conv.last_message.timestamp).strftime('%H:%M, %d-%m-%Y')

            data.append({
                'conversation_id': conv.id,
                'name': conv_name, 
                'avatar_url': conv_avatar_url,
                'last_message': last_message_text,
                'last_message_timestamp': last_message_ts,
                'detail_url': reverse('chat:conversation_detail', kwargs={'conversation_id': conv.id})
            })

        return JsonResponse({'conversations': data})
        
    except Exception as e:
        print(f"Lỗi API Conversations: {e}") # In lỗi ra terminal để debug
        return JsonResponse({'conversations': []}, status=200) # Trả về list rỗng thay vì lỗi 500


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
        # Kiểm tra xem user có avatar không để lấy URL, nếu không thì trả về None
        avatar_url = None
        try:
            if user.avatar:
                avatar_url = user.avatar.url
        except ValueError:
            # Phòng trường hợp trường avatar tồn tại nhưng không có file
            pass

        data.append({
            'id': user.id, 
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'avatar_url': avatar_url, 
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
    
@login_required
def api_get_new_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    
    # Lấy ID của tin nhắn cuối cùng từ phía client gửi lên
    last_message_id = request.GET.get('last_message_id')
    
    if not last_message_id:
        return JsonResponse({'messages': []})

    # Tìm những tin nhắn có ID lớn hơn ID cuối cùng (tức là tin nhắn mới)
    new_messages = conversation.messages.filter(id__gt=last_message_id).exclude(hidden_by=request.user).order_by('timestamp')
    
    data = []
    for msg in new_messages:
        # Format thời gian
        local_ts = timezone.localtime(msg.timestamp)
        formatted_ts = local_ts.strftime('%H:%M, %d-%m-%Y') # Hoặc format theo ý bạn

        file_url = msg.file.url if msg.file else None
        file_type = None
        if msg.file:
            if msg.is_image: file_type = 'image'
            elif msg.is_video: file_type = 'video'
            else: file_type = 'file'

        data.append({
            'message_id': msg.id,
            'sender_id': msg.sender.id if msg.sender else None,
            'sender_avatar': msg.sender.avatar.url if msg.sender and msg.sender.avatar else '/static/images/default.jpg',
            'sender_username': msg.sender.username if msg.sender else 'System',
            'text': msg.text,
            'timestamp': formatted_ts,
            'file_url': file_url,
            'file_type': file_type,
            'is_me': (msg.sender == request.user) # Đánh dấu xem có phải tin của mình không
        })
        
    return JsonResponse({'messages': data})