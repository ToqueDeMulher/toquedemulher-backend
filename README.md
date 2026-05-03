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

## Testes da API com Bruno

Para realizar os testes dos endpoints da API, foi utilizado o **Bruno** como cliente de requisições HTTP.

O Bruno é a ferramenta adotada neste projeto para organizar, executar e versionar os requests da API durante o desenvolvimento. As coleções ficam salvas em arquivos locais, o que facilita o versionamento junto ao código-fonte no repositório. :contentReference[oaicite:0]{index=0}

### Como o Bruno foi utilizado neste projeto

Foi criada uma coleção da API contendo os endpoints desenvolvidos no backend, organizados por módulos. Entre eles:

- autenticação
- usuário
- endereço
- pagamento

Além da organização por pastas, também foi configurado um **environment local** para reutilizar variáveis da aplicação, como a URL base da API e o token JWT de autenticação. O Bruno suporta variáveis de ambiente para tornar os requests reutilizáveis em diferentes contextos. :contentReference[oaicite:1]{index=1}

Exemplo de variáveis utilizadas no ambiente local:

baseUrl=http://127.0.0.1:8000
token=

### Como outros desenvolvedores podem usar o Bruno no projeto

Para utilizar o Bruno neste projeto, os demais desenvolvedores devem seguir os passos abaixo:

1. clonar o repositório do backend na máquina local;
2. instalar o **Bruno**;
3. abrir o Bruno e acessar a coleção salva dentro da pasta do projeto;
4. selecionar o environment configurado para execução local;
5. executar o request de login para obter o token JWT;
6. informar o token na variável `token` do environment;
7. utilizar os demais requests normalmente para testar os endpoints protegidos e públicos da API.

### Estrutura esperada no projeto

A coleção do Bruno deve estar disponível dentro do diretório do backend, por exemplo:

backend/
  bruno/
    auth/
    user/
    address/
    payment/


---

## 📦 Fluxo de cadastro de produtos, fornecedores e estoque

Esta parte do sistema organiza o fluxo administrativo para cadastrar produtos, fornecedores, vincular fornecedores aos produtos e registrar entradas reais no estoque. Os testes dessas rotas estão organizados no **Bruno**, dentro da coleção do projeto, usando a variável `{{baseUrl}}`.

### Ordem recomendada do fluxo

```text
1. Supplier
   Cadastra quem fornece os produtos.

2. Product
   Cadastra o que será vendido na loja.

3. SupplierProduct
   Informa quais fornecedores vendem quais produtos, com preço de custo e prazo.

4. Stock
   Registra a entrada real no estoque e cria as levas/lotes.
```

Essa ordem evita erros como fornecedor inexistente, produto inexistente e inconsistência no estoque.

---

### 1. Criar fornecedor

**Rota:** `POST /supplier`

Cria um fornecedor que poderá ser associado a produtos e utilizado nas entradas de estoque.

#### Exemplo de requisição

```json
{
  "name": "Distribuidora Alpha",
  "contact": "(61) 99999-1111",
  "email": "alpha@distribuidora.com"
}
```

#### Campos recebidos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `name` | string | Sim | Nome do fornecedor |
| `contact` | string | Não | Telefone ou contato do fornecedor |
| `email` | string | Não | E-mail válido do fornecedor |

#### Retorno esperado

```json
{
  "mensagem": "Fornecedor criado com sucesso"
}
```

#### Erros comuns

| Status | Motivo |
|---|---|
| 400 | Já existe fornecedor com esse e-mail |
| 422 | E-mail inválido ou JSON fora do schema |

---

### 2. Criar produto

**Rota:** `POST /products`

Cria um produto que será vendido na loja. A rota também pode receber uma lista de `supplier_products`, permitindo cadastrar junto quais fornecedores vendem esse produto.

#### Exemplo de requisição

```json
{
  "slug": "protetor-solar-loreal-50fps-120ml",
  "name": "Protetor Solar L'Oréal 50FPS 120ml",
  "price": 69.90,
  "active": true,
  "volume": "120ml",
  "target_audience": "Unissex",
  "product_type": "Protetor Solar",
  "skin_type": "Todos os tipos",
  "vegan": false,
  "cruelty_free": true,
  "hypoallergenic": true,
  "spf": 50,
  "brand_id": null,
  "description_id": null,
  "supplier_products": [
    {
      "supplier_name": "Distribuidora Premium",
      "supplier_price": 35.00,
      "lead_time_days": 2
    },
    {
      "supplier_name": "Importadora Luxo",
      "supplier_price": 33.50,
      "lead_time_days": 4
    }
  ]
}
```

#### Campos principais recebidos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `slug` | string | Sim | Identificador público único do produto, usado em URLs |
| `name` | string | Sim | Nome do produto |
| `price` | number | Sim | Preço de venda do produto |
| `active` | boolean | Não | Define se o produto está ativo |
| `volume` | string | Não | Volume ou tamanho do produto |
| `target_audience` | string | Não | Público-alvo do produto |
| `product_type` | string | Não | Tipo do produto |
| `skin_type` | string | Não | Tipo de pele, quando aplicável |
| `hair_type` | string | Não | Tipo de cabelo, quando aplicável |
| `fragrance` | string | Não | Fragrância do produto |
| `spf` | int | Não | Fator de proteção solar |
| `vegan` | boolean | Não | Indica se é vegano |
| `cruelty_free` | boolean | Não | Indica se é cruelty free |
| `hypoallergenic` | boolean | Não | Indica se é hipoalergênico |
| `brand_id` | int/null | Não | ID da marca, se existir |
| `description_id` | int/null | Não | ID da descrição, se existir |
| `supplier_products` | array | Não | Lista de fornecedores que vendem o produto |

#### Campos de `supplier_products`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `supplier_name` | string | Sim | Nome do fornecedor já cadastrado |
| `supplier_price` | number | Sim | Preço de custo do fornecedor |
| `lead_time_days` | int/null | Não | Prazo médio de entrega em dias |

#### Retorno esperado

Dependendo do schema atual da rota, o retorno pode ser uma mensagem ou um objeto do produto criado. O recomendado para o frontend é retornar o produto criado, por exemplo:

```json
{
  "id": "uuid-do-produto",
  "slug": "protetor-solar-loreal-50fps-120ml",
  "name": "Protetor Solar L'Oréal 50FPS 120ml",
  "price": 69.90
}
```

#### Erros comuns

| Status | Motivo |
|---|---|
| 400 | Slug já existe |
| 400 | Fornecedor informado em `supplier_products` não existe |
| 422 | JSON inválido ou campo obrigatório ausente |

---

### 3. Associar fornecedor a vários produtos

**Rota:** `POST /suppliersProducts`

Associa um fornecedor já cadastrado a uma lista de produtos já cadastrados. Essa rota representa o catálogo do fornecedor, ou seja, quais produtos ele vende, por qual preço e com qual prazo.

#### Exemplo de requisição

```json
{
  "supplier_name": "Distribuidora Alpha",
  "products_list": [
    {
      "product_name": "Perfume Versace Eros 100ml",
      "supplier_price": 79.90,
      "lead_time_days": 7
    },
    {
      "product_name": "Perfume Dior Sauvage 100ml",
      "supplier_price": 45.50,
      "lead_time_days": 5
    },
    {
      "product_name": "Creme Hidratante Nivea 200ml",
      "supplier_price": 19.90,
      "lead_time_days": 3
    }
  ]
}
```

#### Campos recebidos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `supplier_name` | string | Sim | Nome do fornecedor já cadastrado |
| `products_list` | array | Sim | Lista de produtos que o fornecedor vende |

#### Campos de `products_list`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `product_name` | string | Sim | Nome exato do produto já cadastrado |
| `supplier_price` | number | Sim | Preço de custo do fornecedor para aquele produto |
| `lead_time_days` | int/null | Não | Prazo médio de entrega em dias |

#### Retorno esperado

```json
{
  "message": "Fornecedor associado aos produtos com sucesso",
  "products_updated": [
    "Perfume Versace Eros 100ml",
    "Perfume Dior Sauvage 100ml",
    "Creme Hidratante Nivea 200ml"
  ]
}
```

#### Erros comuns

| Status | Motivo |
|---|---|
| 400 | Fornecedor não encontrado |
| 400 | Produto não encontrado |
| 422 | JSON inválido ou campo obrigatório ausente |

---

### 4. Adicionar entrada no estoque

**Rota:** `POST /stock/`

Registra uma entrada real de mercadoria no estoque. Cada item enviado cria uma leva/lote em `stock_batch` e atualiza o total disponível em `stock`.

#### Exemplo de requisição

```json
{
  "supplier_name": "Distribuidora Premium",
  "items": [
    {
      "product_name": "Perfume Dior Sauvage 100ml",
      "quantity": 10,
      "unit_cost": 320.50,
      "expiry_date": "2027-12-31"
    },
    {
      "product_name": "Perfume Versace Eros 100ml",
      "quantity": 8,
      "unit_cost": 295.00,
      "expiry_date": "2027-10-15"
    },
    {
      "product_name": "Produto Simples",
      "quantity": 20,
      "unit_cost": 25.00,
      "expiry_date": "2028-01-01"
    }
  ]
}
```

#### Campos recebidos

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `supplier_name` | string | Sim | Nome do fornecedor que entregou os produtos |
| `items` | array | Sim | Lista de produtos que entraram no estoque |

#### Campos de `items`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `product_name` | string | Sim | Nome exato do produto cadastrado |
| `quantity` | int | Sim | Quantidade adicionada ao estoque |
| `unit_cost` | number | Sim | Custo unitário da leva/lote |
| `expiry_date` | date/null | Não | Data de validade no formato `YYYY-MM-DD` |

#### Retorno esperado

```json
{
  "mensagem": "Estoque atualizado"
}
```

#### Erros comuns

| Status | Motivo |
|---|---|
| 400 | Fornecedor não existente |
| 400 | Produto não existente |
| 422 | JSON inválido, quantidade inválida ou data inválida |

---

## 🧪 Organização dos testes no Bruno

No Bruno, a coleção deve deixar o fluxo claro para o time de frontend e backend. A organização recomendada é:

```text
bruno/
  stock/
    01 - supplier.bru
    02 - product.bru
    03 - suppliersProducts.bru
    04 - stock.bru
```

A ordem dos testes deve seguir o fluxo:

```text
POST /supplier
POST /products
POST /suppliersProducts
POST /stock/
```

### Variáveis recomendadas no ambiente local do Bruno

```text
baseUrl=http://127.0.0.1:8000
token=
```

Use `{{baseUrl}}` nas requisições para evitar URLs fixas, por exemplo:

```text
{{baseUrl}}/products
{{baseUrl}}/suppliersProducts
{{baseUrl}}/stock/
```

---

## 🧠 Diferença entre SupplierProduct, StockBatch e Stock

| Entidade | Papel |
|---|---|
| `Supplier` | Cadastra quem fornece produtos |
| `Product` | Cadastra o que será vendido na loja |
| `SupplierProduct` | Informa quais fornecedores vendem quais produtos, com preço e prazo |
| `StockBatch` | Registra uma entrada real de mercadoria, ou seja, uma leva/lote |
| `Stock` | Guarda o total disponível de cada produto |

Resumo:

```text
SupplierProduct = catálogo/possibilidade de compra
StockBatch = compra real/entrada no estoque
Stock = total disponível
```

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
