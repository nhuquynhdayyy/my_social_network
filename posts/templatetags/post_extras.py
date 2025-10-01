from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    # KIỂM TRA XEM 'dictionary' CÓ THỰC SỰ LÀ MỘT DICTIONARY KHÔNG
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    
    # Nếu không phải, trả về None để không gây lỗi
    return None