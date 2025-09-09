# chat/forms.py

from django import forms
from .models import Message

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Nhập tin nhắn của bạn...'
            })
        }
        labels = {
            'text': ''  # Ẩn nhãn của trường text
        }