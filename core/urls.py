from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("evento/<int:pk>/", views.evento, name="evento"),
    path("escala/<int:pk>/responder/", views.responder, name="responder"),
    path("indisponibilidade/", views.indisponibilidade, name="indisponibilidade"),
    path("repertorio/", views.repertorio, name="repertorio"),
]
