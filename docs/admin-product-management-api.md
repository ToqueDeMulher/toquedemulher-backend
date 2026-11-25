# Contrato de gerenciamento de produtos

Esta entrega reutiliza as tabelas `product`, `description`, `category`,
`category_product_link`, `stock`, `stock_movement` e `product_image`. Nenhuma
migração de banco é necessária.

Todas as rotas administrativas exigem um token de usuário com papel `admin`.
Credenciais privilegiadas do Supabase Storage permanecem exclusivamente no
backend.

## Fluxo de cadastro e publicação

`POST /api/v1/products` aceita os campos existentes do produto e também:

- `description`: `{ text, usage_tips?, ingredients? }`;
- `category_ids`: IDs de categorias existentes;
- `stock_quantity`: inteiro maior ou igual a zero.

O produto é sempre criado como rascunho (`active=false`), mesmo quando um
cliente antigo envia `active=true`. Depois do upload das imagens, use
`POST /api/v1/products/{id}/publish`. A API só publica produtos com descrição,
categoria, imagem, preço positivo e estoque positivo. Use `/unpublish` para
retirá-los da vitrine sem apagar histórico ou vínculos com pedidos.

## Consulta e edição

- `GET /products/admin/categories`: opções de categoria.
- `GET /products/admin/all`: lista completa; aceita `search`, `status`
  (`draft` ou `published`) e `category_id`.
- `GET /products/admin/{id}`: dados administrativos completos.
- `PATCH /products/{id}`: altera os campos básicos, descrição, categorias e
  quantidade absoluta em estoque. Ajustes de estoque geram movimento do tipo
  `ADJUSTMENT`.

## Imagens

`POST /products/{id}/images/upload` recebe JPG, PNG ou WEBP. A ordem deve ser
um inteiro positivo; imagens existentes são deslocadas quando uma posição
ocupada é usada. `POST /products/{id}/images/{image_id}/primary` move a imagem
selecionada para a primeira posição. A imagem de ordem 1 é a principal do
catálogo público.

O endpoint legado de exclusão continua disponível por compatibilidade e
recusa produtos com vínculos protegidos. O painel administrativo não o usa:
arquivamento nesta etapa significa retirar o produto da vitrine.
