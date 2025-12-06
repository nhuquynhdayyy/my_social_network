# accounts/context_processors.py

from .models import Friendship, User
from django.db.models import Q

def friends_sidebar_processor(request):
    """
    1. Cung cấp danh sách bạn bè (sidebar_friends_list).
    2. Cung cấp gợi ý kết bạn dựa trên bạn chung (friend_suggestions).
    """
    
    # Nếu chưa đăng nhập thì trả về rỗng ngay
    if not request.user.is_authenticated:
        return {}

    current_user = request.user
    context = {}

    # =======================================================
    # PHẦN 1: LẤY DANH SÁCH BẠN BÈ HIỆN TẠI (Của bạn & Sidebar)
    # =======================================================
    
    # Lấy tất cả mối quan hệ đã ACCEPTED
    friendships = Friendship.objects.filter(
        (Q(from_user=current_user) | Q(to_user=current_user)) & Q(status='ACCEPTED')
    )
    
    # Dùng set (tập hợp) thay vì list để tính toán giao điểm (intersection) sau này
    my_friend_ids = set()
    
    for friendship in friendships:
        if friendship.from_user == current_user:
            my_friend_ids.add(friendship.to_user.id)
        else:
            my_friend_ids.add(friendship.from_user.id)
    
    # Query lấy User object để hiển thị lên Sidebar (Code cũ của bạn)
    # Lấy 7 người ngẫu nhiên
    context['sidebar_friends_list'] = User.objects.filter(id__in=my_friend_ids).order_by('?')[:7]


    # =======================================================
    # PHẦN 2: LOGIC GỢI Ý KẾT BẠN (BẠN CHUNG)
    # =======================================================
    suggestions = []

    # B1: Xác định những ai KHÔNG CẦN gợi ý
    # - Chính mình
    # - Những người đã là bạn (my_friend_ids)
    # - Những người mình ĐÃ GỬI lời mời (nhưng họ chưa đồng ý)
    sent_request_ids = Friendship.objects.filter(
        from_user=current_user, 
        status='PENDING'
    ).values_list('to_user_id', flat=True)

    # Gom tất cả ID cần loại trừ lại
    exclude_ids = my_friend_ids.union(set(sent_request_ids))
    exclude_ids.add(current_user.id)

    # B2: Lấy danh sách Ứng viên (Người lạ)
    # Loại trừ danh sách trên VÀ loại trừ Admin (superuser)
    # Lấy ngẫu nhiên 20 người để kiểm tra (Tránh lấy hết database gây chậm)
    candidates = User.objects.exclude(id__in=exclude_ids).exclude(is_superuser=True).order_by('?')[:20]

    # B3: Soi từng ứng viên xem có bạn chung không
    for stranger in candidates:
        # Lấy danh sách bạn bè của NGƯỜI LẠ (Logic y hệt phần 1)
        stranger_friendships = Friendship.objects.filter(
            (Q(from_user=stranger) | Q(to_user=stranger)) & Q(status='ACCEPTED')
        )
        stranger_friend_ids = set()
        for f in stranger_friendships:
            if f.from_user == stranger:
                stranger_friend_ids.add(f.to_user.id)
            else:
                stranger_friend_ids.add(f.from_user.id)
        
        # --- PHÉP TOÁN TẬP HỢP: TÌM GIAO ĐIỂM (Intersection) ---
        # So sánh tập bạn của Tôi và tập bạn của Người Lạ
        mutual_friends_count = len(my_friend_ids.intersection(stranger_friend_ids))

        # Nếu có ít nhất 1 bạn chung -> Thêm vào danh sách gợi ý
        if mutual_friends_count > 0:
            suggestions.append({
                'user': stranger,
                'mutual_count': mutual_friends_count
            })
    
    # B4: Sắp xếp theo số lượng bạn chung (Nhiều nhất lên đầu)
    # Lấy tối đa 3 người để hiện ở sidebar
    suggestions.sort(key=lambda x: x['mutual_count'], reverse=True)
    context['friend_suggestions'] = suggestions[:3]

    return context