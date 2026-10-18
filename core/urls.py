from django.urls import path
from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("evento/novo/", v.evento_form, name="evento_novo"),
    path("evento/<int:pk>/", v.evento, name="evento"),
    path("evento/<int:pk>/editar/", v.evento_form, name="evento_editar"),
    path("evento/<int:pk>/excluir/", v.evento_excluir, name="evento_excluir"),
    path("evento/<int:pk>/escala/add/", v.escala_add, name="escala_add"),
    path("evento/<int:pk>/setlist/add/", v.setlist_add, name="setlist_add"),
    path("escala/<int:pk>/responder/", v.responder, name="responder"),
    path("escala/<int:pk>/remover/", v.escala_del, name="escala_del"),
    path("setlist/<int:pk>/remover/", v.setlist_del, name="setlist_del"),
    path("setlist/<int:pk>/mover/", v.setlist_mover, name="setlist_mover"),
    path("indisponibilidade/", v.indisponibilidade, name="indisponibilidade"),
    path("repertorio/", v.repertorio, name="repertorio"),
    path("repertorio/nova/", v.musica_form, name="musica_nova"),
    path("repertorio/<int:pk>/editar/", v.musica_form, name="musica_editar"),
    path("repertorio/<int:pk>/excluir/", v.musica_excluir, name="musica_excluir"),
]
