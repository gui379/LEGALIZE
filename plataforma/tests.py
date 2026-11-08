from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import ContratoGerado
from datetime import date
from decimal import Decimal


class LegalizeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='teste', password='SenhaForte123!')
        self.client.force_login(self.user)

    def test_rotas_privadas_exigem_login(self):
        self.client.logout()
        for nome in ('painel', 'historico_contratos', 'gerar_contratos', 'analise_clausulas'):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302)

    def test_logout_requer_post(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)

    def test_documentos_iguais_sao_bloqueados(self):
        dados = {'parte_a': 'Parte A', 'parte_b': 'Parte B', 'doc_a': '123.456.789-00',
                 'doc_b': '12345678900', 'valor': '100.00', 'data': '2026-11-08',
                 'vigencia': '12', 'baixar': '1'}
        response = self.client.post(reverse('gerar_contratos'), dados)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContratoGerado.objects.count(), 0)

    def test_valor_invalido_nao_cria_contrato(self):
        dados = {'valor': 'não-numérico', 'baixar': '1'}
        response = self.client.post(reverse('gerar_contratos'), dados)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContratoGerado.objects.count(), 0)

    def test_usuario_nao_exclui_contrato_de_outro(self):
        outro = get_user_model().objects.create_user(username='outro', password='SenhaForte123!')
        contrato = ContratoGerado.objects.create(usuario=outro, modelo_contrato='civeis',
            parte_a='A', parte_b='B', data=date(2026, 11, 8), valor=Decimal('10.00'))
        self.client.post(reverse('historico_contratos'), {'enviar_lixeira':'1',
            'contrato_id': str(contrato.id), 'justificativa_texto':'teste'})
        contrato.refresh_from_db()
        self.assertFalse(contrato.is_deletado)
