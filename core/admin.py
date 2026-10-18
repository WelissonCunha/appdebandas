from django.contrib import admin
from .models import *


class EscalaInline(admin.TabularInline):
    model = Escala
    extra = 1


class SetlistInline(admin.TabularInline):
    model = ItemSetlist
    extra = 1


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "banda", "tipo", "data_hora")
    list_filter = ("banda", "tipo")
    inlines = [EscalaInline, SetlistInline]


@admin.register(Musica)
class MusicaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "artista", "tom", "bpm", "banda")
    search_fields = ("titulo", "artista")


@admin.register(Membro)
class MembroAdmin(admin.ModelAdmin):
    list_display = ("user", "banda", "papel", "instrumentos")


admin.site.register([Banda, Aviso, Indisponibilidade, Escala])
