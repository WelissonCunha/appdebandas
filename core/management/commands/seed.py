from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import *


class Command(BaseCommand):
    help = "Cria dados de exemplo"

    def handle(self, *a, **k):
        admin = User.objects.create_superuser("admin", "a@a.com", "admin123", first_name="Admin")
        banda = Banda.objects.create(nome="Banda Exemplo", descricao="Banda de demonstração")
        lider = Membro.objects.create(user=admin, banda=banda, papel="lider", instrumentos="Violão, Vocal")
        membros = [lider]
        for nome, inst in [("ana", "Teclado"), ("bruno", "Bateria"), ("carla", "Vocal")]:
            u = User.objects.create_user(nome, password="senha123", first_name=nome.capitalize())
            membros.append(Membro.objects.create(user=u, banda=banda, instrumentos=inst))
        ms = [Musica.objects.create(banda=banda, titulo=t, tom=tom, bpm=bpm)
              for t, tom, bpm in [("Música A", "G", 72), ("Música B", "D", 90), ("Música C", "E", 120)]]
        ev = Evento.objects.create(banda=banda, titulo="Culto de Domingo", tipo="culto", local="Templo principal",
                                   data_hora=timezone.now() + timedelta(days=5))
        for m, f in zip(membros, ["Violão", "Teclado", "Bateria", "Vocal"]):
            Escala.objects.create(evento=ev, membro=m, funcao=f)
        for i, m in enumerate(ms, 1):
            ItemSetlist.objects.create(evento=ev, musica=m, ordem=i)
        Aviso.objects.create(banda=banda, autor=admin, texto="Ensaio geral na sexta, 19h30!", fixado=True)
        self.stdout.write("Pronto. Login: admin/admin123 ou ana/senha123")
