# toquedemulher-backend

Backend em `FastAPI`/`SQLModel` do projeto Toque de Mulher.

## Escopo atual do código versionado

# 📁 Arquitetura do Projeto

Este projeto foi desenvolvido com **FastAPI** e segue uma organização modular para facilitar a manutenção, escalabilidade e separação de responsabilidades.

A estrutura foi pensada para dividir claramente:
- rotas da API;
- configurações centrais;
- integração com banco de dados PostgreSQL;
- models e schemas;
- serviços de negócio.

---

## Estrutura de Pastas

```bash
app/
├── api/
│   ├── v1/endpoints/
│   │   ├── addressRouter.py      # Rotas relacionadas aos endereços do usuário
│   │   ├── login.py              # Rotas de autenticação e login
│   │   ├── router.py             # Roteador principal de agrupamento das rotas
│   │   ├── stripeCheckout.py     # Rotas de integração com Stripe Checkout
│   │   ├── user.py               # Rotas relacionadas aos usuários
│   │   └── weebhook.py           # Webhook para eventos externos (ex: Stripe)
│   └── dependencies.py           # Dependências reutilizáveis da API (auth, sessão, helpers)
│
├── core/
│   ├── db.py                     # Integração com PostgreSQL e gerenciamento da conexão/sessão
│   ├── settings.py               # Configurações globais e variáveis de ambiente
│   └── time.py                   # Funções utilitárias relacionadas a data e hora
│
├── models/                       # Modelos do banco de dados
├── schemas/                      # Schemas de validação e serialização
├── services/                     # Regras de negócio e integrações externas
├── main.py                       # Ponto de entrada da aplicação FastAPI
│
static/                           # Arquivos estáticos, se necessário
.gitignore                        # Arquivos e pastas ignorados pelo Git
README copy.md                    # Cópia/rascunho de documentação
README.md                         # Documentação principal do projeto
database.py                       # Arquivo auxiliar relacionado ao banco de dados
requirements.txt                  # Dependências do projeto

## Configuração local

1. Use o arquivo `toquedemulher-backend/.env`.
2. Se precisar recriar, copie `toquedemulher-backend/.env.example`.
3. Preencha os valores sensíveis antes de subir a API.

Exemplo de execução local:

```bash
cd toquedemulher-backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Variáveis de ambiente

As variáveis atualmente documentadas em `toquedemulher-backend/.env.example` são:

- `SECRET_KEY`: chave secreta usada para autenticação, assinatura de tokens e proteção de dados sensíveis da aplicação
- `FRONTEND_SUCCESS_URL`: URL do front-end para onde o usuário será redirecionado após um pagamento aprovado
- `FRONTEND_PENDING_URL`: URL do front-end para onde o usuário será redirecionado quando o pagamento ficar pendente
- `FRONTEND_FAILURE_URL`: URL do front-end para onde o usuário será redirecionado quando o pagamento falhar ou for cancelado
- `SUPABASE_URL`: URL do projeto Supabase
- `SUPABASE_SERVICE_ROLE_KEY`: chave de serviço do Supabase com permissões elevadas para operações no storage
- `SUPABASE_BUCKET`: nome do bucket do Supabase usado para armazenar imagens dos produtos
- `SUPABASE_FOLDER`: pasta base dentro do bucket onde os uploads dos produtos serão organizados
- `SUPABASE_TIMEOUT`: tempo limite, em segundos, para operações de upload no Supabase
- `PRODUCT_IMAGE_MAX_BYTES`: tamanho máximo permitido, em bytes, para upload de imagens de produtos
- `STRIPE_SECRET_KEY`: chave secreta da Stripe usada para criar sessões de pagamento e realizar operações seguras no backend
- `STRIPE_WEBHOOK_SECRET`: segredo usado para validar a autenticidade dos eventos enviados pela Stripe via webhook

## O que já foi feito

### Segurança e configuração

- proteção reforçada de `.env` no Git com ignore para `.env` e variantes locais
- criação de `toquedemulher-backend/.env.example` com placeholders seguros
- criação local de `toquedemulher-backend/.env` a partir do exemplo

### Compatibilidade e consistência temporal

- substituição de `datetime.utcnow()` por timestamps UTC com timezone via `app/core/time.py`

### Validação de entrada

- validação de e-mail de fornecedor com `EmailStr`
- bloqueio de preços negativos
- bloqueio de quantidades negativas
- bloqueio de ordem de imagem menor que `1`

### Banco de dados

- adição de `CheckConstraint` para valores que não podem ser negativos
- adição de `CheckConstraint` para nota de review entre `1` e `5`
- adição de índices em várias foreign keys para melhorar consultas e joins

### Upload de imagens

- validação de tipos aceitos: JPG, PNG e WEBP
- validação de tamanho máximo por `PRODUCT_IMAGE_MAX_BYTES`
- leitura do arquivo em chunks no fluxo assíncrono
- documentação explícita das respostas `400`, `404`, `413` e `500`

### Robustez transacional

- `rollback` explícito em falhas na criação de produto
- `rollback` explícito em falhas ao persistir imagem após upload

## Validação já executada

Após as alterações, foi validado:

- compilação dos módulos alterados com `python3 -m py_compile`
- checagem de diff com `git diff --check`

## Observações importantes

### Banco já existente

O projeto ainda usa `SQLModel.metadata.create_all(...)` no startup. Isso significa que:

- índices e constraints novos não são aplicados retroativamente em tabelas já existentes
- para ambiente já criado, será necessário fazer migração ou recriar o schema

### Escopo das findings

Nem todas as findings do review estavam representadas no código versionado atual. Neste snapshot, não foram encontrados módulos completos de:

- carrinho com fechamento de compra
- criação completa de pedido
- processamento de pagamento
- autenticação com configuração de bcrypt
- busca de produtos vulnerável a SQL injection

Esses pontos precisam do código correspondente no repositório para correção direta.

## Próximo passo recomendado

Para consolidar as mudanças de banco com segurança, o próximo passo ideal é adicionar migrações formais (por exemplo, com Alembic) em vez de depender apenas de `create_all`.
