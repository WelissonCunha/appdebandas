from django import forms
from .models import Banda, Escala, Evento, ItemSetlist, Membro, Musica

FMT = "%Y-%m-%dT%H:%M"


def bandas_do_lider(user):
    return Banda.objects.filter(membros__user=user, membros__papel="lider")


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = ["banda", "titulo", "tipo", "data_hora", "local", "descricao"]
        widgets = {
            "data_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FMT),
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *a, user=None, **k):
        super().__init__(*a, **k)
        self.fields["banda"].queryset = bandas_do_lider(user)
        self.fields["data_hora"].input_formats = [FMT]


class EscalaForm(forms.ModelForm):
    class Meta:
        model = Escala
        fields = ["membro", "funcao"]
        widgets = {"funcao": forms.TextInput(attrs={"placeholder": "Função (ex.: Bateria)"})}

    def __init__(self, *a, banda, **k):
        super().__init__(*a, **k)
        self.fields["membro"].queryset = Membro.objects.filter(banda=banda).select_related("user")
        self.fields["membro"].label_from_instance = lambda m: m.user.get_full_name() or m.user.username


class SetlistForm(forms.ModelForm):
    class Meta:
        model = ItemSetlist
        fields = ["musica", "tom"]

    def __init__(self, *a, banda, **k):
        super().__init__(*a, **k)
        self.fields["musica"].queryset = Musica.objects.filter(banda=banda)


class MusicaForm(forms.ModelForm):
    class Meta:
        model = Musica
        fields = ["banda", "titulo", "artista", "tom", "bpm", "link", "cifra"]
        widgets = {"cifra": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *a, user=None, **k):
        super().__init__(*a, **k)
        self.fields["banda"].queryset = bandas_do_lider(user)
