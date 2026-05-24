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
 https://docs.google.com/document/d/1N4774-DWwkNtCF7AEbAsxhwpKiUNp7PtfbrS7IxiDHo/edit?usp=sharing
