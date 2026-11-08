"""Experimento 2: 50 threads concorrentes no banco de testes Django.

Execute: python manage.py test plataforma.test_experimento_concorrencia -v 2
Nao modifica o banco de dados normal do projeto.
"""
import csv
import platform
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal
from pathlib import Path

import django
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from .models import ContratoGerado


class ExperimentoConcorrenciaBanco(TransactionTestCase):
    def test_50_threads_concorrentes(self):
        quantidade = 50
        usuario = get_user_model().objects.create_user(
            username='experimento_concorrencia', password='TesteSomenteLocal123!'
        )
        pasta = Path(__file__).resolve().parent.parent / 'evidencias_concorrencia'
        pasta.mkdir(exist_ok=True)
        csv_path = pasta / 'resultado_50_threads.csv'
        resumo_path = pasta / 'resumo_experimento_2.txt'
        barreira = threading.Barrier(quantidade, timeout=30)

        def executar(indice):
            close_old_connections()
            inicio = time.perf_counter()
            try:
                # Todos tentam iniciar a gravacao na mesma janela de tempo.
                barreira.wait()
                ContratoGerado.objects.create(
                    usuario_id=usuario.pk,
                    modelo_contrato='experimento_concorrencia',
                    numero_contrato=f'EXP2-{indice:03d}',
                    ano_contrato='2026',
                    parte_a=f'Parte A {indice}',
                    parte_b=f'Parte B {indice}',
                    data=date(2026, 11, 8),
                    valor=Decimal('100.00'),
                )
                situacao, erro = 'SUCESSO', ''
            except Exception as exc:
                situacao, erro = 'FALHA', f'{type(exc).__name__}: {exc}'
            finally:
                connections.close_all()
            return {'thread': indice, 'situacao': situacao,
                    'tempo_ms': round((time.perf_counter() - inicio) * 1000, 3),
                    'erro': erro}

        inicio_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=quantidade) as pool:
            futuros = [pool.submit(executar, i) for i in range(1, quantidade + 1)]
            resultados = [f.result() for f in as_completed(futuros)]
        total_s = time.perf_counter() - inicio_total
        resultados.sort(key=lambda item: item['thread'])

        registros = list(ContratoGerado.objects.filter(
            usuario=usuario, modelo_contrato='experimento_concorrencia'
        ).values_list('numero_contrato', flat=True))
        sucesso = [r for r in resultados if r['situacao'] == 'SUCESSO']
        falha = [r for r in resultados if r['situacao'] == 'FALHA']
        ids_sucesso = {f"EXP2-{r['thread']:03d}" for r in sucesso}
        ids_banco = set(registros)
        integridade_ok = (len(registros) == len(ids_banco) == len(sucesso)
                         and ids_banco == ids_sucesso)
        tempos = [r['tempo_ms'] for r in resultados]

        with csv_path.open('w', newline='', encoding='utf-8-sig') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=['thread', 'situacao', 'tempo_ms', 'erro'])
            escritor.writeheader()
            escritor.writerows(resultados)

        linhas = [
            'EXPERIMENTO 2 - 50 THREADS CONCORRENTES - LEGALIZE',
            f'Python: {platform.python_version()} | Django: {django.get_version()}',
            f'Banco de teste: {connection.vendor} | Nome: {connection.settings_dict["NAME"]}',
            'Metodo: 50 threads, barreira de inicio, cada uma tenta inserir um contrato distinto.',
            'Ambiente: Django TransactionTestCase; banco temporario de testes; sem HTTP e sem MySQL.',
            f'Threads iniciadas: {quantidade}',
            f'Operacoes bem-sucedidas: {len(sucesso)} | Falhas: {len(falha)}',
            f'Registros persistidos: {len(registros)}',
            f'Integridade dos registros bem-sucedidos: {"OK" if integridade_ok else "FALHOU"}',
            f'Tempo medio por thread: {statistics.mean(tempos):.3f} ms',
            f'Tempo total do lote: {total_s:.3f} s',
            f'CSV: {csv_path}',
            'OBS: Falhas por database is locked sao possiveis no SQLite e devem ser relatadas.',
            'OBS: Este teste nao demonstra capacidade de 50 conexoes simultaneas em MySQL.',
        ]
        resumo_path.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
        print('\n' + '\n'.join(linhas) + '\n')
        if falha:
            print('Amostra de falhas:')
            for item in falha[:5]:
                print(f"  Thread {item['thread']}: {item['erro']}")
        # O teste nao exige 50 sucessos: mede a capacidade REAL, inclusive falhas.
        self.assertEqual(len(resultados), quantidade)
        self.assertTrue(integridade_ok, 'Os registros de operacoes bem-sucedidas nao conferem com o banco.')
