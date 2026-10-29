from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Banda, Indisponibilidade, Membro


class IndisponibilidadeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="musico", password="senha-segura")
        self.banda_a = Banda.objects.create(nome="Banda A")
        self.banda_b = Banda.objects.create(nome="Banda B")
        Membro.objects.create(user=self.user, banda=self.banda_a)
        Membro.objects.create(user=self.user, banda=self.banda_b)
        self.client.force_login(self.user)

    def test_indisponibilidade_is_saved_for_selected_band(self):
        response = self.client.post(
            "/indisponibilidade/",
            {"banda": self.banda_b.pk, "data": "2026-11-15", "motivo": "Viagem"},
        )

        self.assertRedirects(response, "/")
        indisponibilidade = Indisponibilidade.objects.get()
        self.assertEqual(indisponibilidade.membro.banda, self.banda_b)
        self.assertEqual(indisponibilidade.data, date(2026, 11, 15))

    def test_cannot_select_a_band_the_user_does_not_belong_to(self):
        outra_banda = Banda.objects.create(nome="Outra banda")
        response = self.client.post(
            "/indisponibilidade/",
            {"banda": outra_banda.pk, "data": "2026-11-15", "motivo": ""},
        )

        self.assertRedirects(response, "/")
        self.assertFalse(Indisponibilidade.objects.exists())
