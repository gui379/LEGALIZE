# LEGALIZE — revisão incremental (Django)

Esta versão preserva a estrutura original e aplica correções iniciais de segurança, validação e integridade.

## Instalação (Python 3.12+)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py test
python manage.py runserver
```

Abra http://127.0.0.1:8000/ . Para produção, configure `DJANGO_DEBUG=false`, `DJANGO_SECRET_KEY` e `DJANGO_ALLOWED_HOSTS` no ambiente. O arquivo `.env.example` é somente uma referência; o Django não carrega `.env` automaticamente.

## Banco de dados

O padrão continua SQLite para preservar o fluxo local. Para usar MySQL, instale `mysqlclient` e configure `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` e `DB_PORT`. Faça backup antes de migrar dados; `migrate` não transfere dados de SQLite para MySQL.

O banco de dados original **não está incluído** no ZIP de distribuição, por segurança. Faça backup do seu `db.sqlite3` antes de substituir os arquivos.

## E-mail de recuperação

Em desenvolvimento, o backend padrão escreve o e-mail de recuperação no terminal (não envia e-mail real). Configure SMTP via variáveis de ambiente para envio real. O fluxo usa tokens do Django.

## Limitações conhecidas

- Análise de cláusulas, consulta legislativa e assistente jurídico ainda **não** integram IA nem fontes oficiais. As telas informam essa limitação em vez de apresentar resultados fictícios.
- Configurações de preferências ainda não persistem; a tela não deve afirmar que salvou.
- As cláusulas geradas são modelos e requerem revisão jurídica humana.
- A validação de documentos impede duplicação entre as partes, mas **não** comprova validade matemática do CPF/CNPJ.
- Antes de publicar, revise permissões, privacidade/LGPD, retenção de contratos, uploads, SMTP e configurações de implantação.
- O projeto não teve testes de integração executados no ambiente de geração, pois Django não estava instalado e a instalação de dependências estava indisponível. Execute os comandos acima no seu computador.
