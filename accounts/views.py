# accounts/views.py

from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm

class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    # reverse_lazy sẽ đợi cho đến khi URL được load xong
    success_url = reverse_lazy('login') # Chuyển hướng đến trang đăng nhập sau khi đăng ký thành công
    template_name = 'accounts/register.html'