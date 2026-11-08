from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from .models import Usuario, ContratoGerado, ClausulaFavorita
import datetime
import json
import re
import html
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordResetForm

# Imports do ReportLab para construção geométrica do PDF formal
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT


def login_view(request):
    if request.method == 'POST':
        usuario_txt = request.POST.get('usuario')
        senha_txt = request.POST.get('senha')
        user = authenticate(request, username=usuario_txt, password=senha_txt)
        if user is not None:
            login(request, user)
            return redirect('painel')
        else:
            messages.error(request, "Usuário ou senha incorretos.")
    return render(request, 'plataforma/login.html')


def cadastro_view(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        usuario_txt = request.POST.get('usuario')
        senha_txt = request.POST.get('senha')
        confirmar_senha = request.POST.get('confirmar_senha')

        nome = (nome or '').strip()
        email = (email or '').strip().lower()
        usuario_txt = (usuario_txt or '').strip()
        if not nome or not email or not usuario_txt or not senha_txt:
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return render(request, 'plataforma/cadastro.html')
        try:
            validate_password(senha_txt)
        except ValidationError as erro:
            messages.error(request, ' '.join(erro.messages))
            return render(request, 'plataforma/cadastro.html')
        if senha_txt != confirmar_senha:
            messages.error(request, "As senhas informadas não são idênticas.")
            return render(request, 'plataforma/cadastro.html')

        if Usuario.objects.filter(username=usuario_txt).exists():
            messages.error(request, "Nome de usuário já cadastrado.")
        elif Usuario.objects.filter(email=email).exists():
            messages.error(request, "Este endereço de e-mail já está em uso.")
        else:
            user = Usuario.objects.create_user(
                username=usuario_txt,
                password=senha_txt,
                first_name=nome,
                email=email
            )
            login(request, user)
            return redirect('painel')
    return render(request, 'plataforma/cadastro.html')


def esqueceu_senha_view(request):
    if request.method == 'POST':
        form = PasswordResetForm({'email': request.POST.get('email', '')})
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                from_email=None,
                email_template_name='registration/password_reset_email.txt',
                subject_template_name='registration/password_reset_subject.txt',
            )
        messages.success(request, 'Se o endereço estiver cadastrado, as instruções serão enviadas pelo serviço de e-mail configurado. Em desenvolvimento, verifique o terminal.')
    return render(request, 'plataforma/esqueceu_senha.html')


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def painel_view(request):
    return render(request, 'plataforma/painel.html')


@login_required(login_url='login')
def historico_contratos_view(request):
    hoje = timezone.localdate()

    ContratoGerado.objects.filter(
        usuario=request.user,
        is_deletado=True,
        deletado_em__lt=hoje - datetime.timedelta(days=30)
    ).delete()

    if request.method == 'POST':
        if 'enviar_lixeira' in request.POST:
            contrato_id = request.POST.get('contrato_id')
            justificativa = request.POST.get('justificativa_texto')
            if contrato_id and justificativa:
                ContratoGerado.objects.filter(id=contrato_id, usuario=request.user, is_deletado=False).update(
                    is_deletado=True,
                    deletado_em=hoje,
                    justificativa_exclusao=justificativa
                )
                messages.success(request, "Contrato movido para a lixeira.")

        elif 'restaurar_lixeira' in request.POST:
            contrato_id = request.POST.get('contrato_id')
            if contrato_id:
                ContratoGerado.objects.filter(id=contrato_id, usuario=request.user, is_deletado=True).update(
                    is_deletado=False,
                    deletado_em=None,
                    justificativa_exclusao=None
                )
                messages.success(request, "Contrato restaurado com sucesso para o histórico!")

    ativos = ContratoGerado.objects.filter(usuario=request.user, is_deletado=False).order_by('-criado_em')
    lixeira = ContratoGerado.objects.filter(usuario=request.user, is_deletado=True).order_by('-deletado_em')

    for contrato in lixeira:
        dias_passados = (hoje - contrato.deletado_em).days if contrato.deletado_em else 0
        contrato.dias_restantes = max(30 - dias_passados, 0)

    return render(request, 'plataforma/historico_contratos.html', {
        'contratos_salvos': ativos,
        'contratos_lixeira': lixeira
    })


# CORREÇÃO DEFINITIVA DO ERRO: Nome alterado de 'generar' para 'gerar_contratos_view'
@login_required(login_url='login')
def gerar_contratos_view(request):
    preview_texto = None
    dados_form = {}

    clausulas_favoritas = ClausulaFavorita.objects.filter(usuario=request.user)
    clausula_assistente = request.GET.get('clausula_sugerida', '')

    editar_id = request.GET.get('editar_id') or request.POST.get('editar_id')
    if editar_id and request.method == 'GET':
        try:
            contrato_antigo = ContratoGerado.objects.get(id=editar_id, usuario=request.user, is_deletado=False)
            if contrato_antigo.dados_estruturados_json:
                dados_form = json.loads(contrato_antigo.dados_estruturados_json)
        except ContratoGerado.DoesNotExist:
            return redirect('historico_contratos')

    if request.method == 'POST':
        clausula_id_deletar = request.POST.get('clausula_id_remover', '')
        if clausula_id_deletar and 'novo_titulo_biblioteca' not in request.POST and 'baixar' not in request.POST and 'visualizar' not in request.POST:
            ClausulaFavorita.objects.filter(id=clausula_id_deletar, usuario=request.user).delete()
            messages.success(request, "Cláusula removida com sucesso da biblioteca.")
            clausulas_favoritas = ClausulaFavorita.objects.filter(usuario=request.user)
            return render(request, 'plataforma/gerar_contratos.html', {
                'preview_texto': preview_texto, 'dados_form': dados_form,
                'clausulas_favoritas': clausulas_favoritas, 'clausula_assistente': clausula_assistente
            })

        if 'adicionar_direto_biblioteca' in request.POST:
            titulo_nova = request.POST.get('novo_titulo_biblioteca')
            texto_nova = request.POST.get('nova_descricao_biblioteca')
            if titulo_nova and texto_nova:
                ClausulaFavorita.objects.create(usuario=request.user, titulo=titulo_nova, texto=texto_nova)
                messages.success(request, f"Cláusula '{titulo_nova}' adicionada com sucesso!")
            else:
                messages.error(request, "Preencha o título e a descrição.")
            clausulas_favoritas = ClausulaFavorita.objects.filter(usuario=request.user)
            return render(request, 'plataforma/gerar_contratos.html', {
                'preview_texto': preview_texto, 'dados_form': dados_form,
                'clausulas_favoritas': clausulas_favoritas, 'clausula_assistente': clausula_assistente
            })

        tipo_parte_a = request.POST.get('tipo_parte_a', 'PF')
        tipo_parte_b = request.POST.get('tipo_parte_b', 'PF')

        valor_bruto = request.POST.get('valor', '0').strip()
        try:
            valor_decimal = Decimal(valor_bruto.replace(',', '.'))
            if not valor_decimal.is_finite() or valor_decimal < 0 or valor_decimal > Decimal('9999999999.99'):
                raise InvalidOperation
            valor_decimal = valor_decimal.quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            messages.error(request, 'Informe um valor monetário válido e não negativo.')
            return redirect('gerar_contratos')
        valor_formatado = f"{valor_decimal:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        doc_a = re.sub(r'\D', '', request.POST.get('doc_a', ''))
        doc_b = re.sub(r'\D', '', request.POST.get('doc_b', ''))
        if not doc_a or not doc_b or doc_a == doc_b:
            messages.error(request, 'As partes A e B devem possuir CPF/CNPJ preenchidos e diferentes.')
            return redirect('gerar_contratos')
        try:
            data_formatada = datetime.date.fromisoformat(request.POST.get('data', ''))
            meses_vigencia = int(request.POST.get('vigencia', '12'))
            if not 1 <= meses_vigencia <= 1200:
                raise ValueError
        except (ValueError, TypeError):
            messages.error(request, 'Informe uma data válida e uma vigência entre 1 e 1200 meses.')
            return redirect('gerar_contratos')
        data_termino = data_formatada + relativedelta(months=meses_vigencia)
        if not request.POST.get('parte_a', '').strip() or not request.POST.get('parte_b', '').strip():
            messages.error(request, 'Informe os nomes das duas partes.')
            return redirect('gerar_contratos')

        forma_pgto = request.POST.get('forma_pagamento', 'À Vista')
        qtd_parcelas = request.POST.get('qtd_parcelas', '1')
        detalhe_pagamento = f"Parcelado Mensal em {qtd_parcelas}x" if forma_pgto == 'Parcelado Mensal' else forma_pgto

        categoria = request.POST.get('categoria_contrato', 'advocaticios')
        sub_segmento = request.POST.get('sub_segmento_contrato', '')

        numero_contrato = request.POST.get('numero_contrato', '')
        ano_contrato = request.POST.get('ano_contrato', '')
        identificador_instrumento = f"Nº {numero_contrato}/{ano_contrato}" if numero_contrato else ""

        logo_alinhamento = request.POST.get('logo_alinhamento', 'CENTER')
        logo_arquivo = request.FILES.get('logo_file', None)
        if logo_arquivo and (logo_arquivo.size > 2 * 1024 * 1024 or not logo_arquivo.content_type.startswith('image/')):
            messages.error(request, 'A logo deve ser uma imagem de até 2 MB.')
            return redirect('gerar_contratos')

        dados_form = {
            'categoria': categoria, 'sub_segmento': sub_segmento,
            'numero_contrato': numero_contrato, 'ano_contrato': ano_contrato,
            'logo_alinhamento': logo_alinhamento,
            'tipo_parte_a': tipo_parte_a, 'parte_a': request.POST.get('parte_a', ''),
            'representante_a': request.POST.get('representante_a', ''), 'doc_a': doc_a,
            'rg_a': request.POST.get('rg_a', ''), 'ie_a': request.POST.get('ie_a', ''),
            'estado_civil_a': request.POST.get('estado_civil_a', 'Solteiro(a)'),
            'profissao_a': request.POST.get('profissao_a', ''), 'endereco_a': request.POST.get('endereco_a', ''),
            'tipo_parte_b': tipo_parte_b, 'parte_b': request.POST.get('parte_b', ''),
            'representante_b': request.POST.get('representante_b', ''), 'doc_b': doc_b,
            'rg_b': request.POST.get('rg_b', ''), 'ie_b': request.POST.get('ie_b', ''),
            'estado_civil_b': request.POST.get('estado_civil_b', 'Solteiro(a)'),
            'profissao_b': request.POST.get('profissao_b', ''), 'endereco_b': request.POST.get('endereco_b', ''),
            'objeto_detalhado': request.POST.get('objeto_detalhado', ''), 'data': request.POST.get('data', ''),
            'vigencia': request.POST.get('vigencia', '12'), 'valor_puro': valor_bruto, 'valor': valor_formatado,
            'forma_pagamento': forma_pgto, 'qtd_parcelas': qtd_parcelas, 'detalhe_pagamento': detalhe_pagamento,
            'multa_atraso': request.POST.get('multa_atraso', '2'),
            'multa_rescisoria': request.POST.get('multa_rescisoria', ''),
            'foro': request.POST.get('foro', ''), 'clausulas': request.POST.get('clausulas', ''),
            'oab_advogado': request.POST.get('oab_advogado', ''),
            'fase_processual': request.POST.get('fase_processual', ''),
            'porcentagem_exito': request.POST.get('porcentagem_exito', ''),
            'prazo_sigilo': request.POST.get('prazo_sigilo', ''),
            'multa_infracao_nda': request.POST.get('multa_infracao_nda', ''),
            'capital_social': request.POST.get('capital_social', ''),
            'matricula_imovel': request.POST.get('matricula_imovel', ''),
            'responsavel_taxas': request.POST.get('responsavel_taxas', ''),
            'cargo_colaborador': request.POST.get('cargo_colaborador', ''),
            'jornada_trabalho': request.POST.get('jornada_trabalho', ''),
            'ajuda_custo_home': request.POST.get('ajuda_custo_home', ''),
        }

        if tipo_parte_a == 'PJ':
            qualificacao_a_txt = f"A empresa {dados_form['parte_a']}, inscrita no CNPJ sob o nº {dados_form['doc_a']}, com Inscrição Estadual nº {dados_form['ie_a']}, por meio de seu representante legal, Sr(a). {dados_form['representante_a']}, com sede localizada à {dados_form['endereco_a']}"
            assinatura_label_a = f"{dados_form['parte_a']}<br/>CNPJ: {dados_form['doc_a']}<br/>Representante: {dados_form['representante_a']}"
        else:
            qualificacao_a_txt = f"{dados_form['parte_a']}, {dados_form['estado_civil_a']}, profissão: {dados_form['profissao_a']}, portador do RG nº {dados_form['rg_a']} e inscrito no CPF sob o nº {dados_form['doc_a']}, residente e domiciliado à {dados_form['endereco_a']}"
            assinatura_label_a = f"{dados_form['parte_a']}<br/>CPF: {dados_form['doc_a']}"

        if tipo_parte_b == 'PJ':
            qualificacao_b_txt = f"A empresa {dados_form['parte_b']}, inscrita no CNPJ sob o nº {dados_form['doc_b']}, com Inscrição Estadual nº {dados_form['ie_b']}, por meio de seu representante legal, Sr(a). {dados_form['representante_b']}, com sede localizada à {dados_form['endereco_b']}"
            assinatura_label_b = f"{dados_form['parte_b']}<br/>CNPJ: {dados_form['doc_b']}<br/>Representante: {dados_form['representante_b']}"
        else:
            qualificacao_b_txt = f"{dados_form['parte_b']}, {dados_form['estado_civil_b']}, profissão: {dados_form['profissao_b']}, portador do RG nº {dados_form['rg_b']} e inscrito no CPF sob o nº {dados_form['doc_b']}, residente e domiciliado à {dados_form['endereco_b']}"
            assinatura_label_b = f"{dados_form['parte_b']}<br/>CPF: {dados_form['doc_b']}"

        base_titulo = sub_segmento.upper() if sub_segmento else "INSTRUMENTO PARTICULAR DE CONTRATO"
        titulo_selecionado = f"{base_titulo} {identificador_instrumento}".strip()

        preview_texto = (
            f"{titulo_selecionado}\n"
            f"{'=' * 60}\n\n"
            f"DAS PARTES:\n"
            f"CONTRATANTE (Parte A): {qualificacao_a_txt}.\n\n"
            f"CONTRATADO (Parte B): {qualificacao_b_txt}.\n\n"
            f"As partes qualificadas firmam o presente instrumento de comum acordo, regendo-se pelas cláusulas seguintes:\n\n"
            f"CLÁUSULA PRIMEIRA - DO OBJETO E ESPECIFICAÇÕES\n"
            f"O presente instrumento tem como escopo principal: {dados_form['objeto_detalhado']}.\n\n"
        )

        if categoria == 'advocaticios':
            preview_texto += f"O CONTRATADO declara inscrição ativa na OAB sob o nº {dados_form['oab_advogado']}. O patrocínio compreende a fase correspondente a: {dados_form['fase_processual']}. "
            if sub_segmento == 'Contrato de Honorários por Êxito':
                preview_texto += f"Os honorários ad êxito corresponderão a {dados_form['porcentagem_exito']}% do proveito econômico obtido."
            preview_texto += "\n\n"
        elif categoria == 'empresariais':
            if sub_segmento == 'Contrato de Confidencialidade (NDA)':
                preview_texto += f"As informações confidenciais confiadas deverão ser resguardadas pelo prazo restrito de {dados_form['prazo_sigilo']} anos. A quebra de sigilo ensejará pena de multa imediata no valor líquido de R$ {dados_form['multa_infracao_nda']}.\n\n"
            elif sub_segmento == 'Contrato Social e Acordo de Sócios':
                preview_texto += f"O capital social estipulado e subscrito corresponde a R$ {dados_form['capital_social']}.\n\n"
        elif categoria == 'civeis':
            if sub_segmento in ['Contrato de Compra e Venda', 'Contrato de Locação']:
                preview_texto += f"O objeto transacionado encontra-se matriculado sob o nº {dados_form['matricula_imovel']}. As obrigações tributárias assessoriais serão custeadas por: {dados_form['responsavel_taxas']}.\n\n"
        elif categoria == 'trabalho':
            preview_texto += f"O empregado exercerá as funções ligadas ao cargo de {dados_form['cargo_colaborador']}, sob a jornada de {dados_form['jornada_trabalho']}. "
            if sub_segmento == 'Contrato de Teletrabalho (Home Office)':
                preview_texto += f"Adiciona-se ajuda de custo de insumos no valor mensal de R$ {dados_form['ajuda_custo_home']}."
            preview_texto += "\n\n"

        preview_texto += (
            f"CLÁUSULA SEGUNDA - DA VIGÊNCIA\n"
            f"Este contrato possui validade firmada pelo período correspondente a {dados_form['vigencia']} meses.\n\n"
            f"CLÁUSULA TERCEIRA - DO PREÇO E LIQUIDAÇÃO\n"
            f"Estipula-se o valor total de R$ {dados_form['valor']}, a ser quitado via {dados_form['detalhe_pagamento']}.\n\n"
            f"CLÁUSULA QUARTA - DOS ENCARGOS E FORO\n"
            f"Incidirá multa de {dados_form['multa_atraso']}% por atraso. Elegem o foro da Comarca de {dados_form['foro']}.\n"
        )

        if dados_form['clausulas']:
            preview_texto += f"\n{dados_form['clausulas']}\n"

        if 'baixar' in request.POST:
            dados_json_string = json.dumps(dados_form)

            if editar_id:
                ContratoGerado.objects.filter(id=editar_id, usuario=request.user, is_deletado=False).update(
                    numero_contrato=numero_contrato, ano_contrato=ano_contrato,
                    parte_a=dados_form['parte_a'], parte_b=dados_form['parte_b'],
                    data=data_formatada, data_termino=data_termino, valor=valor_decimal,
                    clausulas_adicionais=dados_form['clausulas'], dados_estruturados_json=dados_json_string
                )
            else:
                ContratoGerado.objects.create(
                    usuario=request.user, modelo_contrato=categoria, sub_segmento=sub_segmento,
                    numero_contrato=numero_contrato, ano_contrato=ano_contrato,
                    parte_a=dados_form['parte_a'], parte_b=dados_form['parte_b'],
                    data=data_formatada, data_termino=data_termino, valor=valor_decimal,
                    clausulas_adicionais=dados_form['clausulas'], dados_estruturados_json=dados_json_string
                )

            response = HttpResponse(content_type='application/pdf')
            response[
                'Content-Disposition'] = f'attachment; filename="contrato_{dados_form["numero_contrato"] or "minuta"}.pdf"'

            def SafeParagraph(text, style):
                return Paragraph(str(text), style)

            doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72,
                                    bottomMargin=72)
            story = []
            styles = getSampleStyleSheet()

            style_titulo = ParagraphStyle('T', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=13,
                                          leading=16, alignment=TA_CENTER, spaceAfter=20)
            style_subtitulo = ParagraphStyle('S', fontName='Helvetica-Bold', fontSize=11, leading=14, spaceBefore=12,
                                             spaceAfter=4)
            style_corpo = ParagraphStyle('B', parent=styles['Normal'], fontName='Helvetica', fontSize=11, leading=16,
                                         alignment=TA_JUSTIFY, firstLineIndent=36, spaceAfter=10)
            style_assinatura = ParagraphStyle('G', fontName='Helvetica', fontSize=10, leading=14, alignment=TA_CENTER)

            if logo_arquivo:
                try:
                    img = Image(logo_arquivo)
                    img.drawHeight = 90
                    img.drawWidth = 200
                    if logo_alinhamento == 'LEFT':
                        data_table = [[img, ""]]
                        col_widths = [210, 250]
                    elif logo_alinhamento == 'RIGHT':
                        data_table = [["", img]]
                        col_widths = [250, 210]
                    else:
                        data_table = [["", img, ""]]
                        col_widths = [130, 200, 130]
                    header_table = Table(data_table, colWidths=col_widths)
                    header_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), logo_alinhamento),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 25),
                    ]))
                    story.append(header_table)
                except:
                    pass

            story.append(SafeParagraph(titulo_selecionado, style_titulo))
            story.append(Spacer(1, 10))
            story.append(SafeParagraph("<b>DAS PARTES:</b>", style_subtitulo))
            story.append(SafeParagraph(f"<b>CONTRATANTE (Parte A):</b> {html.escape(qualificacao_a_txt)}.", style_corpo))
            story.append(SafeParagraph(f"<b>CONTRATADO (Parte B):</b> {html.escape(qualificacao_b_txt)}.", style_corpo))
            story.append(SafeParagraph(
                "As partes qualificadas firmam o presente instrumento de comum acordo, regendo-se pelas disposições contidas nas seguintes cláusulas:",
                style_corpo))

            story.append(SafeParagraph("<b>CLÁUSULA PRIMEIRA - DO OBJETO</b>", style_subtitulo))
            story.append(
                SafeParagraph(f"O presente contrato tem por objeto: {html.escape(str(dados_form['objeto_detalhado']))}.", style_corpo))

            if categoria == 'advocaticios':
                story.append(SafeParagraph(
                    f"O Advogado Contratado declara inscrição ativa na OAB sob o nº {html.escape(str(dados_form['oab_advogado']))}, englobando o escopo de atuação na fase de: {html.escape(str(dados_form['fase_processual']))}.",
                    style_corpo))
                if sub_segmento == 'Contrato de Honorários por Êxito':
                    story.append(SafeParagraph(
                        f"Pactua-se cláusula quota-litis ad êxito fixada em {html.escape(str(dados_form['porcentagem_exito']))}% sobre o benefício financeiro auferido.",
                        style_corpo))
            elif categoria == 'empresariais':
                if sub_segmento == 'Contrato de Confidencialidade (NDA)':
                    story.append(SafeParagraph(
                        f"As informações confidenciais confiadas deverão ser resguardadas pelo prazo restrito de {html.escape(str(dados_form['prazo_sigilo']))} anos. A quebra de sigilo ensejará pena de multa cominatória compulsória imediata no valor líquido de R$ {html.escape(str(dados_form['multa_infracao_nda']))}.",
                        style_corpo))
                elif sub_segmento == 'Contrato Social e Acordo de Sócios':
                    story.append(SafeParagraph(
                        f"Fica determinado para fins corporativos que o capital social estipulado e subscrito corresponde a R$ {html.escape(str(dados_form['capital_social']))}.",
                        style_corpo))
            elif categoria == 'civeis':
                story.append(SafeParagraph(
                    f"O imóvel objeto da transação civil encontra-se registrado sob a matrícula de número {html.escape(str(dados_form['matricula_imovel']))}. As obrigações tributárias assessoriais serão custeadas por: {html.escape(str(dados_form['responsavel_taxas']))}.",
                    style_corpo))
            elif categoria == 'trabalho':
                story.append(SafeParagraph(
                    f"O empregado exercerá as funções corporativas ligadas ao cargo de {html.escape(str(dados_form['cargo_colaborador']))}, sob o regime de jornada laboral de {html.escape(str(dados_form['jornada_trabalho']))}.",
                    style_corpo))
                if sub_segmento == 'Contrato de Teletrabalho (Home Office)':
                    story.append(SafeParagraph(
                        f"Por se tratar de trabalho remoto, adiciona-se ajuda de custo de insumos no valor mensal fixo de R$ {html.escape(str(dados_form['ajuda_custo_home']))}.",
                        style_corpo))

            story.append(SafeParagraph("<b>CLÁUSULA SEGUNDA - DA VIGÊNCIA E PRAZOS</b>", style_subtitulo))
            story.append(SafeParagraph(
                f"A vigência contratual é estabelecida por {html.escape(str(dados_form['vigencia']))} meses, com termo final estimado para {data_termino.strftime('%d/%m/%Y')}.",
                style_corpo))
            story.append(SafeParagraph("<b>CLÁUSULA TERCEIRA - DO PREÇO E DA FORMA DE PAGAMENTO</b>", style_subtitulo))
            story.append(SafeParagraph(
                f"Pela execução do objeto pactuado, fixa-se o montante de R$ {html.escape(str(dados_form['valor']))}, liquidado mediante {html.escape(str(dados_form['detalhe_pagamento']))}.",
                style_corpo))
            story.append(SafeParagraph("<b>CLÁUSULA QUARTA - DOS ENCARGOS MORATÓRIOS E FORO</b>", style_subtitulo))
            story.append(SafeParagraph(
                f"Pelo atraso incidirá multa penal moratória de {html.escape(str(dados_form['multa_atraso']))}%. As partes elegem a Comarca de {html.escape(str(dados_form['foro']))} para dirimir eventuais litígios decorrentes.",
                style_corpo))

            if dados_form['clausulas']:
                linhas_clausulas = dados_form['clausulas'].split('\n\n')
                for bloco in linhas_clausulas:
                    if bloco.strip():
                        story.append(SafeParagraph(html.escape(bloco).replace('\n', '<br/>'), style_corpo))

            story.append(Spacer(1, 10))
            story.append(SafeParagraph(
                f"E, por estarem firmes, lavram e assinam o presente instrumento na data de {data_formatada.strftime('%d/%m/%Y')}.",
                style_corpo))

            table_data = [
                [SafeParagraph(f"______________________________________<br/><b>CONTRATANTE</b><br/>{html.escape(assinatura_label_a).replace('&lt;br/&gt;', '<br/>')}",
                           style_assinatura),
                 SafeParagraph(f"______________________________________<br/><b>CONTRATADO</b><br/>{html.escape(assinatura_label_b).replace('&lt;br/&gt;', '<br/>')}",
                           style_assinatura)]
            ]
            sign_table = Table(table_data, colWidths=[230, 230])
            sign_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 40),
            ]))
            story.append(KeepTogether([sign_table]))

            doc.build(story)
            return response

    return render(request, 'plataforma/gerar_contratos.html',
                  {'preview_texto': preview_texto, 'dados_form': dados_form, 'clausulas_favoritas': clausulas_favoritas,
                   'clausula_assistente': clausula_assistente})


@login_required(login_url='login')
def analise_clausulas_view(request):
    resultado = None
    if request.method == 'POST':
        texto = request.POST.get('clausula_texto', '')
        if texto:
            resultado = 'Análise automatizada ainda não configurada. A cláusula foi recebida, mas nenhum risco jurídico foi verificado. Consulte um profissional qualificado.'
    return render(request, 'plataforma/analise_clausulas.html', {'resultado': resultado})


@login_required(login_url='login')
def consulta_legislativa_view(request):
    resultados = None
    if request.method == 'POST':
        termo = request.POST.get('termo', '')
        resultados = f"Consulta por '{termo}': a integração com uma fonte legislativa oficial ainda não foi configurada. Nenhuma lei foi verificada."
    return render(request, 'plataforma/consulta_legislativa.html', {'resultados': resultados})


@login_required(login_url='login')
def assistente_juridico_view(request):
    sugestao = None
    if request.method == 'POST':
        assunto = request.POST.get('assunto', '')
        detalhes = request.POST.get('detalhes', '')
        sugestao = 'O assistente com IA ainda não está integrado. Não é possível gerar uma cláusula jurídica validada automaticamente nesta versão.'
    return render(request, 'plataforma/assistente_juridico.html', {'sugestao': sugestao})


@login_required(login_url='login')
def configuracoes_view(request):
    if request.method == 'POST':
        messages.warning(request, "As preferências ainda não possuem persistência implementada. Nenhuma alteração foi salva.")
    return render(request, 'plataforma/configuracoes.html')