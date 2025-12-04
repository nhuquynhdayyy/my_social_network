from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameBackend(ModelBackend):
    # Cho phép đăng nhập bằng username hoặc email
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Tìm user có username = input HOẶC email = input
            user = User.objects.get(Q(username=username) | Q(email=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Nếu có nhiều user trùng email, lấy user đầu tiên tìm thấy
            user = User.objects.filter(Q(username=username) | Q(email=username)).order_by('id').first()

        # Kiểm tra mật khẩu và xem user có được phép active không
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None