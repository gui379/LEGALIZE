"""Experimento 1 do PI LEGALIZE: 100 geracoes de PDF pela view Django.
Copie para legalize/plataforma/test_experimento_pdf.py e execute:
python manage.py test plataforma.test_experimento_pdf -v 2
"""
import csv
import platform
import statistics
import time
from datetime import date
from pathlib import Path

import django
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ContratoGerado


class ExperimentoCemPDFs(TestCase):
    def test_100_geracoes_pdf(self):
        usuario = get_user_model().objects.create_user(
            username='experimento_pdf', password='SenhaDeTeste123!'
        )
        self.client.force_login(usuario)
        url = reverse('gerar_contratos')
        resultados = []

        inicio_total = time.perf_counter()
        for numero in range(1, 101):
            dados = {
                'baixar': '1',
                'parte_a': 'Pessoa Ficticia A',
                'parte_b': 'Pessoa Ficticia B',
                'doc_a': '111.111.111-11',
                'doc_b': '222.222.222-22',
                'tipo_parte_a': 'PF',
                'tipo_parte_b': 'PF',
                'numero_contrato': str(numero),
                'ano_contrato': '2026',
                'categoria_contrato': 'advocaticios',
                'objeto_detalhado': 'Contrato ficticio para medicao academica.',
                'valor': '100.00',
                'data': date.today().isoformat(),
                'vigencia': '12',
                'foro': 'Ceres',
            }
            inicio = time.perf_counter()
            try:
                resposta = self.client.post(url, dados)
                duracao_ms = (time.perf_counter() - inicio) * 1000
                pdf_valido = (
                    resposta.status_code == 200
                    and resposta.get('Content-Type', '').startswith('application/pdf')
                    and bytes(resposta.content).startswith(b'%PDF-')
                )
                resultados.append({
                    'execucao': numero,
                    'tempo_ms': round(duracao_ms, 3),
                    'status_http': resposta.status_code,
                    'pdf_valido': pdf_valido,
                    'tamanho_bytes': len(resposta.content),
                    'erro': '' if pdf_valido else 'Resposta nao e PDF valido',
                })
            except Exception as erro:
                duracao_ms = (time.perf_counter() - inicio) * 1000
                resultados.append({
                    'execucao': numero,
                    'tempo_ms': round(duracao_ms, 3),
                    'status_http': 'ERRO',
                    'pdf_valido': False,
                    'tamanho_bytes': 0,
                    'erro': f'{type(erro).__name__}: {erro}',
                })
        duracao_total_s = time.perf_counter() - inicio_total

        pasta = Path.cwd() / 'evidencias_pdf'
        pasta.mkdir(exist_ok=True)
        csv_path = pasta / 'resultado_100_pdfs.csv'
        with csv_path.open('w', newline='', encoding='utf-8-sig') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(resultados[0].keys()), delimiter=';')
            escritor.writeheader()
            escritor.writerows(resultados)

        tempos = [item['tempo_ms'] for item in resultados]
        aprovados = sum(item['pdf_valido'] for item in resultados)
        total_registros = ContratoGerado.objects.filter(usuario=usuario).count()
        relatorio = (
            'EXPERIMENTO 1 - 100 GERACOES DE PDF - LEGALIZE\n'
            f'Data: {date.today().isoformat()}\n'
            f'Python: {platform.python_version()} | Django: {django.get_version()}\n'
            'Metodo: 100 requisicoes POST sequenciais via Django Test Client; '
            'inclui validacao, gravacao em banco de teste e geracao PDF.\n'
            'Ambiente: execucao local, sem rede HTTP real, sem concorrencia.\n'
            f'Execucoes: {len(resultados)} | PDFs validos: {aprovados} | Falhas: {100 - aprovados}\n'
            f'Registros criados no banco de teste: {total_registros}\n'
            f'Tempo medio por requisicao: {statistics.mean(tempos):.3f} ms\n'
            f'Tempo minimo: {min(tempos):.3f} ms\n'
            f'Tempo maximo: {max(tempos):.3f} ms\n'
            f'Tempo total: {duracao_total_s:.3f} s\n'
            f'CSV: {csv_path}\n'
        )
        (pasta / 'resumo_experimento_1.txt').write_text(relatorio, encoding='utf-8')
        print('\n' + relatorio, flush=True)
        self.assertEqual(aprovados, 100, 'Nem todas as requisicoes produziram PDFs validos; veja o CSV.')
        self.assertEqual(total_registros, 100, 'Numero inesperado de contratos no banco de teste.')
