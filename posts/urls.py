# posts/urls.py

from django.urls import path
from .views import HomePageView

urlpatterns = [
    # Khi người dùng truy cập vào URL gốc của app này (''),
    # hãy gọi HomePageView
    path('', HomePageView.as_view(), name='home'),
]