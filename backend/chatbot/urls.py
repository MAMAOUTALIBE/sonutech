from django.urls import path
from . import views
app_name = 'chatbot'
urlpatterns = [
    path('assistant/', views.assistant_settings, name='assistant_settings'),
    path('brouillons/', views.draft_list, name='draft_list'),
    path('brouillons/<int:pk>/', views.draft_detail, name='draft_detail'),
    path('prospects/<uuid:pk>/assistant/', views.lead_generate, name='lead_generate'),
]
