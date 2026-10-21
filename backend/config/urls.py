from django.urls import path

from analysis import views

urlpatterns = [
    path("api/health", views.health),
]
