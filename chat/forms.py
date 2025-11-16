# chat/forms.py

from django import forms
from django.contrib.auth import get_user_model
# SỬA Ở ĐÂY: Import cả Message và Conversation
from .models import Message, Conversation

User = get_user_model()


# ==========================================================
# === FORM GỬI TIN NHẮN (ĐÃ TỐI ƯU TỪ CODE CỦA BẠN) ===
# ==========================================================
class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            # Dùng TextInput sẽ phù hợp hơn cho khung chat nhanh
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tin nhắn...',
                'autocomplete': 'off' # Tắt gợi ý của trình duyệt
            })
        }
        labels = {
            'text': ''  # Ẩn nhãn của trường text
        }


# ==========================================================
# === FORM TẠO NHÓM CHAT MỚI (ĐÃ THÊM Ở BƯỚC TRƯỚC) ===
# ==========================================================
class GroupCreationForm(forms.ModelForm):
    # Sử dụng ModelMultipleChoiceField để cho phép chọn nhiều thành viên
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label="Chọn thành viên"
    )

    class Meta:
        model = Conversation
        # Các trường cần thiết để tạo nhóm
        fields = ['name', 'avatar', 'participants']
        labels = {
            'name': 'Tên nhóm',
            'avatar': 'Ảnh đại diện nhóm',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên nhóm...'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }

    def __init__(self, *args, **kwargs):
        # Lấy user đang đăng nhập từ view để loại bỏ họ khỏi danh sách lựa chọn
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            # Không cho phép người dùng tự chọn chính mình vào nhóm
            self.fields['participants'].queryset = User.objects.exclude(pk=self.user.pk)