from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from content import views as content
from inquiries.views import SubmitInquiry, ManageInquiries
from accounts import views as accounts
from agent import views as agent
from chatbot.api import chat

public = DefaultRouter()
for name, view in [('services', content.PublicServices), ('slides', content.PublicSlides), ('sectors', content.PublicSectors), ('courses', content.PublicCourses), ('settings', content.PublicSettings), ('inquiries', SubmitInquiry)]:
    public.register(name, view, basename='public-' + name)
private = DefaultRouter()
for name, view in [('services', content.ManageServices), ('slides', content.ManageSlides), ('sectors', content.ManageSectors), ('courses', content.ManageCourses), ('settings', content.ManageSettings), ('images', content.ManageImages), ('inquiries', ManageInquiries), ('users', accounts.ManageUsers), ('groups', accounts.ManageGroups), ('permissions', accounts.ManagePermissions), ('audit-logs', accounts.ManageAudit), ('leads', agent.ManageLeads), ('agent-triages', agent.ManageTriages), ('agent-drafts', agent.ManageDrafts)]:
    private.register(name, view, basename='manage-' + name)
urlpatterns = [path('api/v1/crm/', include('crm.api_urls')), path('api/v1/public/chat/', chat, name='public-chat'), path('crm/', include('chatbot.urls')), path('crm/', include('crm.urls')), path('api/v1/public/', include(public.urls)), path('api/v1/agent/approval/<str:token>/', agent.approval, name='agent-approval'), path('api/v1/manage/', include(private.urls)), path('api/v1/auth/csrf/', accounts.CsrfView.as_view()), path('api/v1/auth/login/', accounts.LoginView.as_view()), path('api/v1/auth/logout/', accounts.LogoutView.as_view()), path('api/v1/auth/me/', accounts.MeView.as_view()), path('api/v1/schema/', SpectacularAPIView.as_view(permission_classes=[IsAuthenticated]), name='schema'), path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema', permission_classes=[IsAuthenticated]))]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
