from django.urls import path

from analysis import views

urlpatterns = [
    path("api/health", views.health),
    path("api/repos/<str:owner>/<str:repo>/report", views.report),
]
