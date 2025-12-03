from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    # Ghi đè trường email để bắt buộc nhập (required=True)
    email = forms.EmailField(required=True, label="Email Address")
    
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    # Hàm này giúp kiểm tra xem email đã tồn tại trong database chưa
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng bởi một tài khoản khác.")
        return email

class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'avatar', 'cover_photo', 'bio', 'birth_date')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].disabled = True

class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)
        
        # Sửa nhãn (Label) hiển thị
        self.fields['username'].label = "Tên đăng nhập hoặc Email"
        
        # (Tùy chọn) Thêm class CSS cho đẹp nếu muốn
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nhập username hoặc email của bạn'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Nhập mật khẩu'
        })