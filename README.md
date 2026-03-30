# toquedemulher-backend

Backend em `FastAPI`/`SQLModel` do projeto Toque de Mulher.

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

## ✅ O que já foi feito

Até o momento, o projeto já possui uma base sólida de back-end em **FastAPI**, com integração entre autenticação, banco de dados, pagamentos e organização modular por camadas.

### Funcionalidades implementadas

- **CRUD de usuários**
  - criação de usuário;
  - consulta de dados do usuário;
  - atualização de informações;
  - estrutura preparada para gerenciamento de contas.

- **CRUD de endereços**
  - criação de endereço vinculado ao usuário autenticado;
  - listagem de endereços;
  - atualização de endereço;
  - remoção de endereço.

- **Login com JWT**
  - autenticação baseada em token;
  - proteção de rotas com usuário autenticado;
  - reaproveitamento das dependências de autenticação.

- **Integração com PostgreSQL**
  - conexão com banco centralizada;
  - criação e persistência de entidades;
  - uso de models para representar as tabelas.

- **Integração com Stripe**
  - configuração inicial de pagamento;
  - criação da base para fluxo de checkout;
  - webhook para recebimento de eventos externos.

- **Separação entre models, schemas, rotas e services**
  - models para estrutura do banco;
  - schemas para validação de entrada e saída;
  - services para lógica de negócio;
  - endpoints organizados por responsabilidade.

---

## 📂 Estrutura já implementada

### `app/api/v1/endpoints/`
Camada responsável pelos endpoints principais da aplicação.

- `addressRouter.py`  
  Responsável pelas rotas de **endereços**, incluindo operações de criação, listagem, atualização e exclusão.

- `login.py`  
  Responsável pela autenticação do usuário e geração de token JWT.

- `router.py`  
  Arquivo central que reúne e registra os endpoints da versão da API.

- `stripeCheckout.py`  
  Responsável pela integração de checkout com a Stripe.

- `user.py`  
  Responsável pelas rotas relacionadas ao usuário.

- `weebhook.py`  
  Responsável pelo recebimento de webhooks, especialmente eventos de pagamento.

---

### `app/core/`
Camada de infraestrutura central da aplicação.

- `db.py`  
  Responsável pela **integração com PostgreSQL**, gerenciamento da conexão, sessão e persistência no banco.

- `settings.py`  
  Centraliza as variáveis de ambiente e configurações gerais do projeto.

- `time.py`  
  Contém utilitários relacionados a data e hora utilizados na aplicação.

---

## 🗄️ Models já estruturados

A pasta `models/` já conta com diversas entidades do domínio do e-commerce, representando o banco de dados da aplicação.

- `address.py`
- `brand.py`
- `cart.py`
- `cartItem.py`
- `category.py`
- `categoryProductLink.py`
- `coupon.py`
- `description.py`
- `order.py`
- `orderCouponLink.py`
- `orderItem.py`
- `payment.py`
- `paymentItem.py`
- `paymentMethod.py`
- `product.py`
- `productImage.py`
- `productReview.py`
- `stock.py`
- `supplier.py`
- `user.py`

Esses arquivos mostram que o projeto já possui modelagem para:
- usuários;
- endereços;
- carrinho;
- pedidos;
- pagamentos;
- produtos;
- estoque;
- fornecedores;
- categorias;
- avaliações;
- cupons.

---

## 🧾 Schemas já criados

A pasta `schemas/` já possui os modelos de **request** e **response** usados para validação e padronização da API.

- `addresses.py`
- `brands.py`
- `categories.py`
- `create_checkout.py`
- `create_products.py`
- `descriptions.py`
- `message.py`
- `payments.py`
- `product_images.py`
- `products.py`
- `stock.py`
- `suppliers.py`
- `user.py`

Isso indica que a aplicação já possui estrutura para:
- validação dos dados recebidos;
- definição de respostas padronizadas;
- separação entre o modelo do banco e o contrato da API.

---

## ⚙️ Services já implementados

A pasta `services/` já concentra parte da lógica de negócio da aplicação.

- `checkoutService.py`  
  Responsável pela lógica do fluxo de checkout e pagamento.

- `loginService.py`  
  Responsável pela autenticação, geração e validação de JWT.

- `service.py`  
  Arquivo auxiliar/base para regras de serviço compartilhadas.

---

## 🧱 Base do sistema já pronta

Com base na estrutura atual, o projeto já possui:

- autenticação com JWT funcionando;
- integração com PostgreSQL estruturada;
- CRUD de usuário implementado;
- CRUD de endereço implementado;
- integração inicial com Stripe;
- organização modular em rotas, schemas, models e services;
- modelagem de entidades principais do e-commerce;
- base pronta para expansão de pedidos, pagamentos, produtos e carrinho.

---

## 🚀 Estado atual do projeto

O projeto já passou da fase inicial de configuração e hoje possui uma **base funcional de back-end para e-commerce em FastAPI**, com:

- arquitetura modular;
- autenticação;
- persistência em banco;
- validação de dados;
- organização escalável;
- preparação para fluxo completo de compra e pagamento.
