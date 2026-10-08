from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, mixins
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from accounts.models import AuditLog
from accounts.permissions import ActionModelPermission
from .models import Service, Slide, Sector, Course, SiteSettings, ImageAsset
from .serializers import ServiceSerializer, SlideSerializer, SectorSerializer, CourseSerializer, SettingsSerializer, ImageSerializer

class PublicContent(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None
    lookup_field = 'slug'
    def get_queryset(self):
        return self.queryset.filter(published=True)

class AuditedManagement(viewsets.ModelViewSet):
    permission_classes = [ActionModelPermission]
    def audit(self, instance, action, fields=()):
        AuditLog.objects.create(actor=self.request.user, action=action, resource=instance._meta.label, object_id=str(instance.pk), changed_fields=sorted(fields))
    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save()
        self.audit(instance, 'create', serializer.validated_data.keys())
    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.save()
        self.audit(instance, 'update', serializer.validated_data.keys())
    @transaction.atomic
    def perform_destroy(self, instance):
        self.audit(instance, 'delete')
        instance.delete()

class PublicServices(PublicContent):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
class PublicSlides(PublicContent):
    queryset = Slide.objects.all()
    serializer_class = SlideSerializer
class PublicSectors(PublicContent):
    queryset = Sector.objects.all()
    serializer_class = SectorSerializer
class PublicCourses(PublicContent):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        return qs.filter(category=category) if category else qs
class PublicSettings(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [AllowAny]
    authentication_classes = []
    queryset = SiteSettings.objects.all()
    serializer_class = SettingsSerializer
    @extend_schema(responses=SettingsSerializer(many=False))
    def list(self, request):
        obj = self.queryset.first()
        if not obj:
            return Response({'detail': 'Configuration indisponible.'}, status=503)
        return Response(self.get_serializer(obj).data)
class ManageServices(AuditedManagement):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
class ManageSlides(AuditedManagement):
    queryset = Slide.objects.all()
    serializer_class = SlideSerializer
class ManageSectors(AuditedManagement):
    queryset = Sector.objects.all()
    serializer_class = SectorSerializer
class ManageCourses(AuditedManagement):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
class ManageSettings(AuditedManagement):
    queryset = SiteSettings.objects.all()
    serializer_class = SettingsSerializer
    http_method_names = ['get', 'patch', 'put', 'head', 'options']
class ManageImages(AuditedManagement):
    queryset = ImageAsset.objects.all()
    serializer_class = ImageSerializer
