# Diagnostico do Supabase

Execute `python scripts/audit_supabase.py` com a conexao configurada no `.env`.
O comando compara 24 tabelas com os modelos atuais, incluindo colunas, tipos,
nulabilidade, chaves primarias e estrangeiras, indices e constraints nomeadas.
Tambem confere RLS, constraints validadas, tabelas extras em public, indices parciais,
o registro de migrations e o bucket de imagens configurado.
Ele usa uma transacao somente de leitura e nao imprime credenciais nem dados pessoais.

Para gerar a consulta de estrutura para o SQL Editor, execute:

```bash
python scripts/audit_supabase.py --export-sql docs/supabase-schema-audit.sql
```

O SQL exportado verifica a estrutura em `public`. O comando com conexao verifica
tambem o historico de migrations e o bucket. Uma lista de findings vazia cobre
apenas os itens verificados; nao certifica todos os dados, policies ou fluxos.
Constraints CHECK sao identificadas por nome; uma regra equivalente com outro
nome precisa de revisao antes de qualquer correcao.

## Correcoes aplicadas em 13/09/2026

- `20260913170000`: adiciona as duas validacoes de cartoes ausentes e cria
  `product-images` se nao existir. O bucket e publico, aceita JPG/PNG/WebP e tem
  limite de 5 MB, conforme o backend. Uma configuracao existente e preservada.
- `20260913171000`: inicializa registros de estoque ausentes com quantidade zero,
  conforme o valor padrao do modelo. Saldos existentes sao preservados.

- `20260913173000`: adiciona nove checks para quantidades e valores, dois indices
  unicos parciais de endereco padrao, remove cinco indices que duplicavam a chave
  primaria e preserva a tabela antiga vazia em `tdm_archive.paymentitem`. O schema
  de arquivo nao permite acesso pelos papeis anon e authenticated.

As migrations foram aplicadas e registradas em transacoes no Supabase remoto.
Nenhum registro de cliente foi alterado ou apagado.

O produto ativo precisa de uma imagem e de sua quantidade real de estoque.
O `.env` local precisa de `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` para
permitir uploads pelo backend. Essas credenciais devem permanecer fora do Git.


## Verificacao das protecoes

```bash
python scripts/verify_supabase_integrity.py
```

O comando cria sete tabelas temporarias a partir das tabelas reais e verifica
12 protecoes: nove checks e unicidade dos padroes de entrega, cobranca e pagamento.
Confere rejeicao de valores invalidos e permite padroes para usuarios distintos.
Nao altera linhas reais nem usa sequencias de producao; as tabelas temporarias
sao eliminadas ao encerrar a transacao. Tambem verifica o arquivo privado e a
remocao dos indices redundantes.

Resultado da revisao de 13/09/2026: auditoria sem findings, 12 protecoes aprovadas
no PostgreSQL e 37 testes do backend aprovados. Os testes usam SQLite e desativam
SMTP real. O backend da branch `feat/backend-improvements` inclui a ordem de
flush e o bloqueio por usuario necessarios para trocar padroes com indices unicos.
A criacao de produto pelo backend passa a inicializar seu estoque com zero.
