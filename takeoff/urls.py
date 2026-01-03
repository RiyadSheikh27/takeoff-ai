"""
Takeoff app URLs
"""
from django.urls import path
from . import views

app_name = 'takeoff'

urlpatterns = [
    path('', views.index, name='index'),
    path('process/', views.process_pdf, name='process'),
    path('download/<str:file_type>/<str:filename>/', views.download_file, name='download'),
]