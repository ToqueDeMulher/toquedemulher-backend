# O Toque de Mulher — Backend API

Backend completo para o e-commerce de beleza e perfumes **O Toque de Mulher**, desenvolvido com **Python + FastAPI** e banco de dados **PostgreSQL**.

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

## Conexão com Supabase

O backend usa SQLAlchemy/SQLModel com Postgres. Para apontar para a Supabase,
crie um `.env` a partir de `.env.example` e preencha uma das opções:

- `DATABASE_URL` com a connection string completa do dashboard da Supabase.
- Ou `SUPABASE_PROJECT_REF` + `SUPABASE_DB_PASSWORD`, para o backend montar a URL direta `db.<project-ref>.supabase.co`.

Use conexão direta para backend persistente com IPv6. Em ambientes IPv4-only,
use a URL do Supavisor em session mode no `DATABASE_URL`. Se usar Supavisor
transaction mode na porta `6543`, defina `DB_POOL_MODE=null`.

Para validar sem expor segredos:

```bash
python scripts/check_supabase_connection.py
```

## Login com Google

O endpoint `POST /api/v1/user/google` recebe o `credential` emitido pelo
Google Identity Services, valida o ID token e emite os tokens JWT do backend.

Configure no `.env`:

```env
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
```

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
