from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from .models import User

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Embed role and financial-visibility flag directly in the JWT payload."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['can_see_financials'] = user.can_see_financials
        token['full_name'] = user.get_full_name()
        return token

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'department', 'phone', 'license_number']
        read_only_fields = ['id']

class UserProfileSerializer(serializers.ModelSerializer):
    """Minimal public profile — no sensitive role data."""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'department']
