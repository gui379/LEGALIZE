"""Experimento 3 LEGALIZE: validar regra RNE-007 com casos controlados.
Coloque em legalize/plataforma/test_experimento_rne007.py.
Execute: python manage.py test plataforma.test_experimento_rne007 -v 2
"""
import csv
import platform
from datetime import date
from pathlib import Path

import django
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ContratoGerado


class ExperimentoRNE007(TestCase):
    def test_cenarios_identificacao_partes(self):
        usuario = get_user_model().objects.create_user(
            username='experimento_rne007', password='SenhaDeTeste123!'
        )
        self.client.force_login(usuario)
        url = reverse('gerar_contratos')
        # Documentos exclusivamente ficticios. A regra compara digitos,
        # nao valida os digitos verificadores de CPF/CNPJ.
        cenarios = [
            ('CPF identico', '12345678900', '12345678900', False),
            ('CPF igual com pontuacao', '123.456.789-00', '12345678900', False),
            ('CPF igual com formatos invertidos', '12345678900', '123.456.789-00', False),
            ('CNPJ identico', '11222333000181', '11222333000181', False),
            ('CNPJ igual com pontuacao', '11.222.333/0001-81', '11222333000181', False),
            ('Documento A vazio', '', '22222222222', False),
            ('Documento B vazio', '11111111111', '', False),
            ('Ambos vazios', '', '', False),
            ('CPF diferentes', '11111111111', '22222222222', True),
            ('CNPJ diferentes', '11222333000181', '11222333000182', True),
            ('CPF e CNPJ distintos', '11111111111', '11222333000181', True),
        ]
        resultados = []
        for indice, (cenario, doc_a, doc_b, deve_aceitar) in enumerate(cenarios, 1):
            antes = ContratoGerado.objects.filter(usuario=usuario).count()
            dados = {
                'baixar': '1', 'parte_a': 'Parte A Ficticia',
                'parte_b': 'Parte B Ficticia', 'doc_a': doc_a, 'doc_b': doc_b,
                'tipo_parte_a': 'PF', 'tipo_parte_b': 'PF',
                'numero_contrato': str(indice), 'ano_contrato': '2026',
                'categoria_contrato': 'advocaticios',
                'objeto_detalhado': 'Teste academico da regra RNE-007.',
                'valor': '100.00', 'data': date.today().isoformat(),
                'vigencia': '12', 'foro': 'Ceres',
            }
            try:
                resposta = self.client.post(url, dados)
                depois = ContratoGerado.objects.filter(usuario=usuario).count()
                pdf = (resposta.status_code == 200
                       and resposta.get('Content-Type', '').startswith('application/pdf')
                       and bytes(resposta.content).startswith(b'%PDF-'))
                aceito = pdf and depois == antes + 1
                rejeitado = resposta.status_code == 302 and depois == antes
                passou = aceito if deve_aceitar else rejeitado
                detalhe = f'HTTP {resposta.status_code}; novos registros: {depois - antes}; PDF: {pdf}'
            except Exception as erro:
                passou = False
                detalhe = f'{type(erro).__name__}: {erro}'
            resultados.append({
                'caso': indice, 'cenario': cenario,
                'esperado': 'ACEITAR' if deve_aceitar else 'REJEITAR',
                'resultado': 'CONFORME' if passou else 'DIVERGENTE',
                'detalhes': detalhe,
            })
            print(f'Caso {indice:02d} | {cenario}: {resultados[-1]["resultado"]} | {detalhe}')

        pasta = Path.cwd() / 'evidencias_rne007'
        pasta.mkdir(exist_ok=True)
        csv_path = pasta / 'resultado_rne007.csv'
        with csv_path.open('w', newline='', encoding='utf-8-sig') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(resultados[0]), delimiter=';')
            escritor.writeheader()
            escritor.writerows(resultados)
        conformes = sum(r['resultado'] == 'CONFORME' for r in resultados)
        relatorio = (
            'EXPERIMENTO 3 - VALIDACAO DA REGRA RNE-007 - LEGALIZE\n'
            f'Data: {date.today().isoformat()}\n'
            f'Python: {platform.python_version()} | Django: {django.get_version()}\n'
            'Metodo: requisicoes POST sequenciais via Django Test Client; '\
            'comparacao de documentos normalizados e persistencia de contratos.\n'
            'Ambiente: local; banco de teste temporario SQLite; sem rede HTTP externa.\n'
            f'Cenarios: {len(resultados)} | Conformes: {conformes} | Divergentes: {len(resultados) - conformes}\n'
            f'Registros criados: {ContratoGerado.objects.filter(usuario=usuario).count()}\n'
            'Escopo: compara identificadores apos remover pontuacao; '\
            'NAO verifica digitos de CPF/CNPJ nem identidade real.\n'
            f'CSV: {csv_path}\n'
        )
        (pasta / 'resumo_experimento_3.txt').write_text(relatorio, encoding='utf-8')
        print('\n' + relatorio)
        self.assertEqual(conformes, len(resultados), 'Ha cenarios divergentes: confira CSV e log.')
