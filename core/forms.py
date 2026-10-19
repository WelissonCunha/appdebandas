from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from .models import Aviso, Banda, Escala, Evento, ItemSetlist, Membro, Musica

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


class MembroForm(forms.ModelForm):
    class Meta:
        model = Membro
        fields = ["papel", "instrumentos"]


class MembroNovoForm(forms.Form):
    banda = forms.ModelChoiceField(queryset=Banda.objects.none())
    username = forms.CharField(max_length=150, label="Login",
                               help_text="Se o login já existir, a pessoa só é adicionada à banda.")
    nome = forms.CharField(max_length=150, required=False, label="Nome")
    senha = forms.CharField(widget=forms.PasswordInput, required=False,
                            help_text="Senha provisória, só para login novo. Peça para a pessoa trocar em 🔑 Senha.")
    papel = forms.ChoiceField(choices=Membro.PAPEIS)
    instrumentos = forms.CharField(max_length=200, required=False, help_text="Ex.: Violão, Vocal")

    def __init__(self, *a, user=None, **k):
        super().__init__(*a, **k)
        self.fields["banda"].queryset = bandas_do_lider(user)


class BandaForm(forms.ModelForm):
    class Meta:
        model = Banda
        fields = ["nome", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}


class AvisoForm(forms.ModelForm):
    class Meta:
        model = Aviso
        fields = ["banda", "texto", "fixado"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *a, user=None, **k):
        super().__init__(*a, **k)
        self.fields["banda"].queryset = bandas_do_lider(user)


class SenhaForm(PasswordChangeForm):
    def clean_new_password1(self):
        s = self.cleaned_data["new_password1"]
        if len(s) < 8:
            raise forms.ValidationError("Use pelo menos 8 caracteres.")
        return s


class SenhaResetForm(forms.Form):
    nova_senha = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Nova senha",
                                 help_text="Mínimo de 8 caracteres.")
    confirmar = forms.CharField(widget=forms.PasswordInput, label="Confirmar nova senha")

    def clean(self):
        d = super().clean()
        if d.get("nova_senha") and d.get("nova_senha") != d.get("confirmar"):
            self.add_error("confirmar", "As senhas não coincidem.")
        return d
