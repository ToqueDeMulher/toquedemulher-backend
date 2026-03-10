# toquedemulher-backend

Backend em `FastAPI`/`SQLModel` do projeto Toque de Mulher.

## Escopo atual do código versionado

No snapshot atual deste repositório, o backend expõe principalmente o módulo de produtos:

- criação de produtos
- upload de imagens de produtos
- modelos centrais de banco com `SQLModel`
- configuração por variáveis de ambiente

Atualmente a aplicação monta a rota de produtos em `app/main.py`.

## Estrutura principal

- `app/main.py`: inicialização da API, CORS, pasta estática e registro das rotas
- `app/core/settings.py`: leitura das variáveis de ambiente
- `app/core/db.py`: engine, modelos centrais e criação de tabelas
- `app/core/time.py`: helper para timestamps UTC com timezone
- `app/features/products/router.py`: endpoints de produto e upload
- `app/features/products/service.py`: slug, upload e regras auxiliares
- `app/features/products/models.py`: modelos de produto e relacionamentos
- `app/features/products/schemas.py`: payloads e validações de entrada

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

- `DATABASE_URL`: conexão do banco
- `SQL_ECHO`: habilita logs SQL
- `CORS_ORIGINS`: origens permitidas separadas por vírgula
- `SUPABASE_URL`: URL do projeto Supabase
- `SUPABASE_SERVICE_ROLE_KEY`: chave de serviço do Supabase
- `SUPABASE_BUCKET`: bucket de imagens
- `SUPABASE_FOLDER`: pasta base dos uploads
- `SUPABASE_TIMEOUT`: timeout de upload
- `PRODUCT_IMAGE_MAX_BYTES`: tamanho máximo permitido para upload

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
