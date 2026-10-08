from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from content.views import AuditedManagement
from inquiries.throttles import LoginThrottle
from drf_spectacular.utils import extend_schema, inline_serializer
from .models import AuditLog
from .permissions import ActionModelPermission

class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    @extend_schema(responses=inline_serializer(name='CSRF', fields={'csrfToken': serializers.CharField()}))
    def get(self, request):
        return Response({'csrfToken': get_token(request)})

@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginThrottle]
    @extend_schema(request=inline_serializer(name='LoginRequest', fields={'username': serializers.CharField(), 'password': serializers.CharField(write_only=True)}), responses=inline_serializer(name='LoginResponse', fields={'id': serializers.IntegerField(), 'username': serializers.CharField(), 'csrfToken': serializers.CharField()}))
    def post(self, request):
        username = request.data.get('username', '')
        password = request.data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 150 or len(password) > 1000:
            return Response({'detail': 'Identifiants invalides.'}, status=400)
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({'detail': 'Identifiants invalides.'}, status=401)
        login(request, user)
        return Response({'id': user.pk, 'username': user.username, 'csrfToken': get_token(request)})
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=204)
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(responses=inline_serializer(name='CurrentUser', fields={'id': serializers.IntegerField(), 'username': serializers.CharField(), 'permissions': serializers.ListField(child=serializers.CharField())}))
    def get(self, request):
        return Response({'id': request.user.pk, 'username': request.user.username, 'permissions': sorted(request.user.get_all_permissions())})

class SuperuserOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and request.user.is_superuser)
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, max_length=1000)
    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'groups', 'password']
    def validate(self, attrs):
        if not self.instance and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Mot de passe requis.'})
        if 'password' in attrs:
            try:
                user = self.instance or get_user_model()(username=attrs.get('username', ''), email=attrs.get('email', ''))
                validate_password(attrs['password'], user=user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'password': exc.messages})
        return attrs
    def create(self, validated_data):
        groups = validated_data.pop('groups', [])
        password = validated_data.pop('password')
        user = get_user_model().objects.create_user(password=password, **validated_data)
        user.groups.set(groups)
        return user
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance
class ManageUsers(AuditedManagement):
    queryset = get_user_model().objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [SuperuserOnly]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions']
class ManageGroups(AuditedManagement):
    queryset = Group.objects.all().order_by('id')
    serializer_class = GroupSerializer
    permission_classes = [SuperuserOnly]
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type']
class ManagePermissions(viewsets.ReadOnlyModelViewSet):
    queryset = Permission.objects.all().order_by('id')
    serializer_class = PermissionSerializer
    permission_classes = [SuperuserOnly]
class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
class ManageAudit(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditSerializer
    permission_classes = [ActionModelPermission]
