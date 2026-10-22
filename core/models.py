from django.conf import settings
from django.db import models

TONS = [(t, t) for t in ["C","C#","D","Eb","E","F","F#","G","Ab","A","Bb","B"]]


class Banda(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome


class Membro(models.Model):
    PAPEIS = [("lider", "Líder"), ("membro", "Membro")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membros")
    banda = models.ForeignKey(Banda, on_delete=models.CASCADE, related_name="membros")
    papel = models.CharField(max_length=10, choices=PAPEIS, default="membro")
    instrumentos = models.CharField(max_length=200, blank=True, help_text="Ex.: Violão, Baixo, Vocal")

    class Meta:
        unique_together = ("user", "banda")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.banda})"


class Musica(models.Model):
    banda = models.ForeignKey(Banda, on_delete=models.CASCADE, related_name="musicas")
    titulo = models.CharField(max_length=150)
    artista = models.CharField(max_length=150, blank=True)
    tom = models.CharField(max_length=3, choices=TONS, blank=True)
    bpm = models.PositiveIntegerField(null=True, blank=True)
    link = models.URLField(blank=True, help_text="YouTube/Spotify")
    cifra = models.TextField(blank=True)

    class Meta:
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo


class Evento(models.Model):
    TIPOS = [("ensaio", "Ensaio"), ("culto", "Culto/Missa"), ("show", "Show"), ("outro", "Outro")]
    banda = models.ForeignKey(Banda, on_delete=models.CASCADE, related_name="eventos")
    titulo = models.CharField(max_length=150)
    tipo = models.CharField(max_length=10, choices=TIPOS, default="ensaio")
    data_hora = models.DateTimeField()
    local = models.CharField(max_length=150, blank=True)
    descricao = models.TextField(blank=True)

    class Meta:
        ordering = ["data_hora"]

    def __str__(self):
        return f"{self.titulo} - {self.data_hora:%d/%m/%Y}"


class Escala(models.Model):
    STATUS = [("pendente", "Pendente"), ("confirmado", "Confirmado"), ("recusado", "Recusado")]
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="escalas")
    membro = models.ForeignKey(Membro, on_delete=models.CASCADE, related_name="escalas")
    funcao = models.CharField(max_length=60, help_text="Ex.: Bateria, Vocal 1")
    status = models.CharField(max_length=12, choices=STATUS, default="pendente")
    obs = models.CharField(max_length=200, blank=True, help_text="Motivo / pedido de troca")

    def __str__(self):
        return f"{self.membro} - {self.funcao}"


class ItemSetlist(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name="setlist")
    musica = models.ForeignKey(Musica, on_delete=models.CASCADE)
    ordem = models.PositiveIntegerField(default=1)
    tom = models.CharField(max_length=3, choices=TONS, blank=True, help_text="Vazio = tom original")

    class Meta:
        ordering = ["ordem"]

    @property
    def tom_final(self):
        return self.tom or self.musica.tom


class Aviso(models.Model):
    banda = models.ForeignKey(Banda, on_delete=models.CASCADE, related_name="avisos")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    texto = models.TextField()
    fixado = models.BooleanField(default=False)
    criado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fixado", "-criado"]


class Indisponibilidade(models.Model):
    membro = models.ForeignKey(Membro, on_delete=models.CASCADE, related_name="indisponibilidades")
    data = models.DateField()
    motivo = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["data"]


class Perfil(models.Model):
    """Dados extras do usuário; trocar_senha força a troca no próximo acesso."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    trocar_senha = models.BooleanField(default=False)
    notif_email = models.BooleanField(default=True)
    notif_push = models.BooleanField(default=True)

    def __str__(self):
        return f"Perfil de {self.user}"


class TrocaEscala(models.Model):
    STATUS = [("aberta", "Aberta"), ("aceita", "Aceita"), ("cancelada", "Cancelada")]
    escala = models.ForeignKey(Escala, on_delete=models.CASCADE, related_name="trocas")
    solicitante = models.ForeignKey(Membro, on_delete=models.CASCADE, related_name="trocas_pedidas")
    destinatario = models.ForeignKey(Membro, null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="trocas_recebidas", help_text="Vazio = qualquer membro da banda")
    substituto = models.ForeignKey(Membro, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="trocas_aceitas")
    motivo = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="aberta")
    criado = models.DateTimeField(auto_now_add=True)
    resolvida = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criado"]


class PushSub(models.Model):
    """Aparelho/navegador inscrito para receber notificações push."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subs")
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    criado = models.DateTimeField(auto_now_add=True)
