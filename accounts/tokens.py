from django.contrib.auth.tokens import PasswordResetTokenGenerator
# Đã xóa import six

class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Thay six.text_type bằng str
        return (
            str(user.pk) + str(timestamp) +
            str(user.is_active)
        )
    
account_activation_token = AccountActivationTokenGenerator()