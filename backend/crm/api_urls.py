from django.urls import path
from rest_framework.routers import DefaultRouter
from . import api
router = DefaultRouter()
for resource, view in [('prospects', api.Prospects), ('clients', api.Clients), ('opportunities', api.Opportunities), ('projects', api.Projects), ('quotes', api.Quotes), ('invoices', api.Invoices), ('appointments', api.Appointments), ('tasks', api.Tasks), ('documents', api.Documents), ('emails', api.Emails), ('users', api.Users), ('inquiries', api.Inquiries)]:
    router.register(resource, view, basename='crm-api-' + resource)
urlpatterns = [path('bootstrap/', api.Bootstrap.as_view(), name='crm-api-bootstrap'), path('settings/', api.SettingsView.as_view()), path('assistant/', api.AssistantView.as_view()), path('assistant/test/', api.AssistantTest.as_view()), *router.urls]
