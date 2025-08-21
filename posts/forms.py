# posts/forms.py

from django import forms
from .models import Post

class PostCreateForm(forms.ModelForm):
    # 1. Khai báo field với widget cơ bản nhất để vượt qua kiểm tra của Django
    media_files = forms.FileField(
        widget=forms.FileInput, # Chỉ dùng lớp Widget, không khởi tạo
        required=False,
        label="Thêm ảnh/video"
    )

    class Meta:
        model = Post
        fields = ['content', 'privacy']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Bạn đang nghĩ gì?', 'class': 'form-control'}),
            'privacy': forms.Select(attrs={'class': 'form-select'}),
        }

    # 2. Dùng hàm __init__ để tùy chỉnh lại widget sau khi form đã được khởi tạo
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bây giờ, chúng ta mới thêm thuộc tính 'multiple' vào widget
        self.fields['media_files'].widget.attrs.update({
            'multiple': True,
            'class': 'form-control'
        })