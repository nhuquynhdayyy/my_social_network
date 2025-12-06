from django import template
from django.utils.html import format_html
from django.urls import reverse
import re

from django.contrib.auth import get_user_model
User = get_user_model()

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    
    return None

@register.filter(name='linkify_mentions')
def linkify_mentions(text):
    """
    Tìm tất cả các chuỗi @username trong văn bản và biến chúng thành link
    dẫn đến trang cá nhân của user đó, nếu user tồn tại.
    """
    # Regex để tìm @ + các ký tự hợp lệ cho username
    pattern = r'@([\w.@+-]+)'
    
    # Lấy danh sách tất cả các username được tag trong text
    usernames = re.findall(pattern, text)
    
    if not usernames:
        return text

    # Query một lần duy nhất để tìm các user tồn tại trong DB
    existing_users = User.objects.filter(username__in=usernames).values_list('username', flat=True)
    
    # Tạo một dictionary để tra cứu nhanh
    existing_users_set = set(existing_users)
    
    def replace_mention(match):
        username = match.group(1)
        # Chỉ tạo link nếu username thực sự tồn tại
        if username in existing_users_set:
            url = reverse('accounts:profile', kwargs={'username': username})
            return format_html('<a href="{}" class="mentioned-user">@{}</a>', url, username)
        else:
            # Nếu user không tồn tại, giữ nguyên text gốc
            return match.group(0)

    # Thay thế tất cả các mention tìm thấy
    linked_text = re.sub(pattern, replace_mention, text)
    return format_html(linked_text)

@register.filter(name='linkify_hashtags')
def linkify_hashtags(text):
    """
    Biến #tag thành đường link
    """
    if not text: return ""
    
    # Regex tìm #tag
    pattern = r"#(\w+)"
    
    def replace_tag(match):
        tag_name = match.group(1)
        # Đường dẫn đến trang danh sách bài viết theo tag
        url = reverse('posts:tag_detail', kwargs={'slug': tag_name.lower()})
        return format_html('<a href="{}" class="fw-bold text-decoration-none">#{}</a>', url, tag_name)

    linked_text = re.sub(pattern, replace_tag, text)
    return format_html(linked_text)