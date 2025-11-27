from django import forms
from django.contrib.auth import get_user_model
from .models import Message, Conversation

User = get_user_model()

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text', 'file'] # Thêm 'file'
        widgets = {
            'text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập tin nhắn...',
                'autocomplete': 'off'
            }),
            # Input file sẽ ẩn đi, được trigger bằng icon
            'file': forms.FileInput(attrs={'class': 'd-none', 'id': 'chat-file-input'})
        }
        labels = { 'text': '', 'file': '' }

class GroupCreationForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label="Chọn thành viên"
    )

    class Meta:
        model = Conversation
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
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['participants'].queryset = User.objects.exclude(pk=self.user.pk)

    def clean_participants(self):
        participants = self.cleaned_data['participants']
        if len(participants) < 2:
            raise forms.ValidationError("Vui lòng chọn ít nhất 2 thành viên khác để tạo nhóm.")
        return participants

class AdminSettingsForm(forms.ModelForm):
    class Meta:
        model = Conversation
        fields = ['admin_only_management']
        labels = { 'admin_only_management': 'Bật chế độ kiểm duyệt (Chỉ Admin mới được thay đổi thông tin nhóm & thêm/duyệt thành viên)' }

class GroupUpdateForm(forms.ModelForm):
    class Meta:
        model = Conversation
        fields = ['name', 'avatar']
        labels = {
            'name': 'Tên nhóm',
            'avatar': 'Ảnh đại diện nhóm'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }

class AddMembersForm(forms.Form):
    new_members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        label="Chọn thành viên để mời",
        required=True
    )
    def __init__(self, *args, **kwargs):
        conversation = kwargs.pop('conversation', None)
        super().__init__(*args, **kwargs)
        if conversation:
            existing_ids = set(conversation.participants.values_list('id', flat=True))
            pending_ids = set(conversation.membership_requests.values_list('user_to_add_id', flat=True))
            exclude_ids = existing_ids.union(pending_ids)
            
            self.fields['new_members'].queryset = User.objects.exclude(id__in=exclude_ids)