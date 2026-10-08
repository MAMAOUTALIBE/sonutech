from django.urls import path
from . import views

app_name = 'crm'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('connexion/', views.login_view, name='login'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('activer/', views.activate, name='activate'),
    path('prospects/', views.prospect_list, name='prospect_list'),
    path('prospects/nouveau/', views.prospect_create, name='prospect_create'),
    path('prospects/<uuid:pk>/', views.prospect_detail, name='prospect_detail'),
    path('prospects/<uuid:pk>/modifier/', views.prospect_edit, name='prospect_edit'),
    path('prospects/<uuid:pk>/notes/', views.note_create, name='note_create'),
    path('demandes/<uuid:pk>/importer/', views.inquiry_import, name='inquiry_import'),
    path('rendez-vous/', views.appointment_list, name='appointment_list'),
    path('rendez-vous/nouveau/', views.appointment_create, name='appointment_create'),
    path('rendez-vous/<int:pk>/modifier/', views.appointment_edit, name='appointment_edit'),
    path('a-faire/', views.task_list, name='task_list'),
    path('a-faire/nouveau/', views.task_create, name='task_create'),
    path('a-faire/<int:pk>/modifier/', views.task_edit, name='task_edit'),
    path('a-faire/<int:pk>/terminer/', views.task_toggle, name='task_toggle'),
]
