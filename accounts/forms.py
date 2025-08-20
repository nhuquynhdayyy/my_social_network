# accounts/forms.py (CODE ĐÃ SỬA ĐÚNG)

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
    # BỎ ĐOẠN __init__ Ở ĐÂY

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'avatar', 'cover_photo', 'bio', 'birth_date')

    # DI CHUYỂN ĐOẠN __init__ VÀO ĐÚNG FORM NÀY
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Vô hiệu hóa trường username, người dùng sẽ thấy nhưng không sửa được
        self.fields['username'].disabled = True