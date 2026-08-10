# O Toque de Mulher — Backend API

Backend completo para o e-commerce de beleza e perfumes **O Toque de Mulher**, desenvolvido com **Python + FastAPI** e banco de dados **PostgreSQL**.

## Inicio rapido

Use dois terminais: um para o backend e outro para o frontend.

Terminal do backend:

```bash
cd toquedemulher-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_supabase_connection.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

A API fica em:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

Se o servidor ja estiver rodando e voce alterar o `.env`, reinicie o backend.
Variaveis de ambiente sao carregadas na inicializacao do processo.

## Tecnologias

| Tecnologia | Versão | Finalidade |
| :--- | :--- | :--- |
| Python | 3.11+ | Linguagem principal |
| FastAPI | 0.115 | Framework web assíncrono |
| SQLAlchemy | 2.0 | ORM para banco de dados |
| Alembic | 1.14 | Migrações de banco de dados |
| PostgreSQL | 15+ | Banco de dados relacional |
| Pydantic v2 | 2.10 | Validação de dados e schemas |
| JWT (python-jose) | 3.3 | Autenticação stateless |
| Passlib (bcrypt) | 1.7 | Hash seguro de senhas |
| Mercado Pago SDK | 2.2 | Processamento de pagamentos |

## Funcionalidades

- **Autenticação:** Registro, login, refresh token, recuperação de senha via email
- **Usuários:** Perfil, endereços, upload de avatar, troca de senha
- **Produtos:** Catálogo com filtros, busca, paginação, variantes e imagens
- **Categorias:** Hierarquia de categorias com subcategorias
- **Carrinho:** Adicionar, atualizar, remover itens com validação de estoque
- **Pedidos:** Criação de pedidos com snapshot de endereço e produtos
- **Pagamentos:** PIX, Boleto e Cartão de Crédito via Mercado Pago + Webhook
- **Avaliações:** Sistema de reviews com fotos, verificação de compra e moderação
- **Emails:** Boas-vindas, confirmação de pedido, envio e redefinição de senha
- **Admin:** Endpoints protegidos para gestão de produtos, pedidos e usuários

## Configuracao local

Crie um arquivo `.env` na raiz de `toquedemulher-backend`. Nao commite esse
arquivo.

Exemplo:

```env
DATABASE_URL=postgresql://postgres.<project-ref>:<senha>@aws-0-ca-central-1.pooler.supabase.com:5432/postgres?sslmode=require
SECRET_KEY=troque-por-uma-chave-forte
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
```

Variaveis principais:

- `DATABASE_URL`: connection string do Postgres/Supabase.
- `SECRET_KEY`: chave usada para assinar JWTs.
- `GOOGLE_CLIENT_ID`: OAuth Client ID web do Google.
- `VITE_GOOGLE_CLIENT_ID`: fallback aceito pelo backend caso a variavel do frontend tenha sido copiada para o servidor.
- `CORS_ORIGINS`: origens permitidas, por padrao inclui `http://localhost:5173` e `http://127.0.0.1:5173`.

## Conexão com Supabase

O backend usa SQLAlchemy/SQLModel com Postgres. Para apontar para a Supabase,
crie um `.env` e preencha uma das opções:

- `DATABASE_URL` com a connection string completa do dashboard da Supabase.
- Ou `SUPABASE_PROJECT_REF` + `SUPABASE_DB_PASSWORD`, para o backend montar a URL direta `db.<project-ref>.supabase.co`.

Use conexão direta para backend persistente com IPv6. Em ambientes IPv4-only,
use a URL do Supavisor em session mode no `DATABASE_URL`. Se usar Supavisor
transaction mode na porta `6543`, defina `DB_POOL_MODE=null`.

Para validar sem expor segredos:

```bash
python scripts/check_supabase_connection.py
```

Neste projeto a Supabase esta sendo usada como Postgres. A autenticacao atual
e propria do FastAPI, com usuarios e JWTs do backend. Nao e necessario ativar
o provider Google em Supabase Auth para o fluxo atual.

## Login com Google

O endpoint `POST /api/v1/user/google` recebe o `credential` emitido pelo
Google Identity Services, valida o ID token e emite os tokens JWT do backend.

Configure no `.env`:

```env
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
```

O backend também aceita `VITE_GOOGLE_CLIENT_ID` como fallback para ambientes
em que a mesma variável pública do frontend foi usada na configuração do
servidor.

Nao use `GOOGLE_CLIENT_SECRET` neste fluxo. O frontend usa Google Identity
Services para obter um ID token, e o backend valida esse token pelo Client ID.

Se a API retornar:

```json
{"detail": "Login com Google nao configurado"}
```

entao o processo do backend iniciou sem `GOOGLE_CLIENT_ID` ou
`VITE_GOOGLE_CLIENT_ID`. Confirme o `.env`, reinicie o backend e, em deploy,
cadastre a variavel de ambiente no painel da plataforma.

Com uma credencial falsa, a API configurada deve responder:

```json
{"detail": "Credential do Google invalida"}
```

Isso indica que o Client ID foi carregado e que apenas o token enviado nao e
valido.

## Template de confirmacao de e-mail

O template de confirmacao do Supabase Auth local/self-hosted esta em:

```text
supabase/templates/confirmation.html
```

Ele e referenciado em `supabase/config.toml`:

```toml
[auth.email.template.confirmation]
subject = "Confirm your email address"
content_path = "./supabase/templates/confirmation.html"
```

Conteudo atual:

```html
<h2>Confirm your email address</h2>

<p>Follow the link below to confirm this email address and finish signing up.</p>
<p><a href="{{ .ConfirmationURL }}">Confirm email address</a></p>
```

Em projeto hosted da Supabase, cole o mesmo HTML no Dashboard em
`Authentication > Email Templates > Confirm signup`. Em projetos free criados
depois de 3 de junho de 2026, a Supabase pode exigir SMTP proprio para
customizar templates.

## Login e acesso admin

A tela de login nao possui mais botao "entrar como admin" ou "entrar como
cliente". O login e unico.

O redirecionamento para `/admin` acontece automaticamente quando o usuario
autenticado tem `role = "admin"` no backend. Usuarios comuns sao enviados para
o perfil.

## Enderecos e checkout

O frontend consome os endpoints de endereco do backend:

- `GET /api/v1/addresses/`
- `POST /api/v1/addresses/`
- `PUT /api/v1/addresses/{address_id}`
- `DELETE /api/v1/addresses/{address_id}`

No checkout, se o usuario logado ja tiver um endereco salvo, o frontend usa o
endereco padrao de entrega. Caso contrario, mostra a opcao de adicionar um novo
endereco e salvar no perfil.

## Testes e verificacao

Rode os testes automatizados:

```bash
source .venv/bin/activate
python -m pytest tests/test_auth.py -q
```

Verifique a API local:

```bash
curl http://127.0.0.1:8000/health
```

Verifique o Google Login sem usar credencial real:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/user/google \
  -H "Content-Type: application/json" \
  -d '{"credential":"fake"}'
```

Se o backend estiver configurado, a resposta sera `Credential do Google
invalida`, nao `Login com Google nao configurado`.

## Estrutura do Projeto

```text
app/                 Código da API FastAPI
app/api/v1/          Rotas HTTP versionadas
app/api/v1/experimental/ Rotas não registradas, mantidas só como referência
app/core/            Configuração, segurança, banco e utilitários centrais
app/models/          Modelos persistidos no banco
app/schemas/         Schemas de entrada e saída
app/services/        Regras de negócio e integrações externas
alembic/             Migrações Alembic legadas
supabase/            Configuração e migrations usadas pela integração Supabase
scripts/             Scripts operacionais
docs/api-client/     Coleções de teste de API, incluindo Bruno
tests/               Testes automatizados
static/uploads/      Arquivos servidos localmente em desenvolvimento
```
