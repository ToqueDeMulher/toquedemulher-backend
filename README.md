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

## Estrutura do Projeto

```
toquedemulher-backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py        # Registro, login, tokens
│   │       │   ├── users.py       # Perfil e endereços
│   │       │   ├── products.py    # Catálogo e categorias
│   │       │   ├── cart.py        # Carrinho de compras
│   │       │   ├── orders.py      # Pedidos
│   │       │   ├── payments.py    # Webhook de pagamentos
│   │       │   └── reviews.py     # Avaliações de produtos
│   │       ├── deps.py            # Dependências (auth guards)
│   │       └── router.py          # Roteador principal
│   ├── core/
│   │   ├── config.py              # Configurações da aplicação
│   │   └── security.py            # JWT e hashing de senhas
│   ├── db/
│   │   └── base.py                # Configuração do SQLAlchemy
│   ├── models/                    # Modelos do banco de dados
│   ├── schemas/                   # Schemas Pydantic (DTOs)
│   ├── services/
│   │   ├── email_service.py       # Envio de emails
│   │   └── payment_service.py     # Integração Mercado Pago
│   └── main.py                    # Ponto de entrada da aplicação
├── alembic/                       # Migrações de banco de dados
├── scripts/
│   └── seed.py                    # Dados iniciais
├── tests/
│   └── test_auth.py               # Testes de autenticação
├── .env.example                   # Exemplo de variáveis de ambiente
├── alembic.ini                    # Configuração do Alembic
└── requirements.txt               # Dependências Python
```

## Instalação e Configuração

### Pré-requisitos

- Python 3.11+
- PostgreSQL 15+
- pip

### Passo a Passo

**1. Clonar o repositório:**
```bash
git clone https://github.com/ToqueDeMulher/toquedemulher-backend.git
cd toquedemulher-backend
```

**2. Criar e ativar ambiente virtual:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

**3. Instalar dependências:**
```bash
pip install -r requirements.txt
```

**4. Configurar variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

**5. Criar o banco de dados PostgreSQL:**
```sql
CREATE DATABASE toquedemulher;
```

**6. Executar as migrações:**
```bash
alembic revision --autogenerate -m "initial migration"
alembic upgrade head
```

**7. Popular com dados iniciais (opcional):**
```bash
python scripts/seed.py
```

**8. Iniciar o servidor:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API estará disponível em `http://localhost:8000`.

## Documentação da API

Com o servidor rodando, acesse:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Endpoints Principais

| Método | Endpoint | Descrição | Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Registrar novo usuário | Não |
| `POST` | `/api/v1/auth/login` | Login e obter tokens | Não |
| `POST` | `/api/v1/auth/refresh` | Renovar access token | Não |
| `POST` | `/api/v1/auth/forgot-password` | Solicitar redefinição de senha | Não |
| `GET` | `/api/v1/users/me` | Ver perfil do usuário | Sim |
| `PUT` | `/api/v1/users/me` | Atualizar perfil | Sim |
| `GET` | `/api/v1/products/` | Listar produtos | Não |
| `GET` | `/api/v1/products/{slug}` | Detalhe do produto | Não |
| `GET` | `/api/v1/products/categories` | Listar categorias | Não |
| `GET` | `/api/v1/cart/` | Ver carrinho | Sim |
| `POST` | `/api/v1/cart/items` | Adicionar item ao carrinho | Sim |
| `POST` | `/api/v1/orders/` | Criar pedido | Sim |
| `GET` | `/api/v1/orders/` | Listar meus pedidos | Sim |
| `POST` | `/api/v1/reviews/` | Criar avaliação | Sim |
| `GET` | `/api/v1/reviews/product/{id}` | Ver avaliações do produto | Não |

## Executar Testes

```bash
pip install pytest
pytest tests/ -v
```

## Variáveis de Ambiente

Consulte o arquivo `.env.example` para a lista completa de variáveis necessárias.

As variáveis mais importantes são:

| Variável | Descrição |
| :--- | :--- |
| `DATABASE_URL` | URL de conexão com o PostgreSQL |
| `SECRET_KEY` | Chave secreta para assinar tokens JWT (mínimo 32 caracteres) |
| `MERCADOPAGO_ACCESS_TOKEN` | Token de acesso do Mercado Pago |
| `SMTP_USER` / `SMTP_PASSWORD` | Credenciais para envio de emails |

## Contribuição

1. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
2. Commit suas mudanças: `git commit -m 'feat: adiciona nova funcionalidade'`
3. Push para a branch: `git push origin feature/nova-funcionalidade`
4. Abra um Pull Request

---

Desenvolvido com 💄 para **O Toque de Mulher**