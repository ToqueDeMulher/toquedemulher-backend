# Diagnostico do Supabase

Execute `python scripts/audit_supabase.py` com a conexao configurada no `.env`.
O comando compara as 26 tabelas dos modelos atuais, incluindo colunas, tipos,
nulabilidade, chaves primarias e estrangeiras, indices e constraints nomeadas.
Tambem confere RLS, constraints validadas, tabelas extras em public, indices parciais,
o registro de migrations e o bucket de imagens configurado. Quando a estrutura
esta correta, o comando conectado tambem identifica produtos sem registro de estoque.
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

## Revisao de acesso em 09/11/2026

O login administrativo foi renovado e o projeto `TDM - Supabase` foi confirmado
como `ACTIVE_HEALTHY`. As verificacoes remotas foram executadas por HTTPS com
`supabase db query --linked`, pois a conexao TCP desta rede continuou expirando.
O host, a porta e o usuario configurados correspondem aos dados atuais do pooler.
As restricoes de rede estao aplicadas com IPv4 e IPv6 liberados.
Nao ha enderecos IPv4 na lista de bloqueios automaticos do projeto.

A auditoria de estrutura das 26 tabelas retornou uma lista vazia de findings.
As 12 protecoes de integridade passaram no PostgreSQL com tabelas temporarias.
Todas as tabelas publicas tem RLS ativado, sem policies de acesso direto para
clientes anon/authenticated. O bucket publico `product-images` aceita
JPG/PNG/WebP e limita uploads a 5 MB. Foram observadas 14 conexoes de um limite
de 60, sem sessoes `idle in transaction`.

A verificacao dos dados encontrou tres produtos ativos sem registro de estoque,
todos sem lotes ou movimentacoes. A migration
`20261109114647_repair_missing_product_stock.sql` criou os registros com quantidade
inicial zero, preservando os saldos e timestamps existentes. A aplicacao e o
registro no historico ocorreram na mesma transacao. A consulta posterior confirmou
zero produtos sem estoque e as 12 migrations locais registradas no remoto.
Quantidade inicial zero nao substitui o cadastro do inventario fisico pela loja.

A repeticao da migration foi testada em tabelas temporarias: nao duplica registros
e preserva um saldo existente de 17 unidades. Nenhum pedido, cadastro de cliente,
lote ou movimentacao real foi alterado.

Correcoes locais:

- Pool automatico: `NullPool` na Vercel e no Supavisor transaction mode, com
  selecao explicita ainda disponivel por `DB_POOL_MODE`.
- Timeouts positivos de conexao e espera pelo pool, ambos configuraveis e com
  padrao de 10 segundos. O timeout de conexao do driver e por tentativa/endereco.
- Scripts operacionais usam o mesmo timeout e fecham as conexoes. Erros de
  conexao e URLs invalidas sao tratados sem imprimir credenciais.
- O verificador de integridade respeita a migration
  `20260917191822_remove_unused_legacy_tables.sql`: verifica a ausencia das
  tabelas legadas e de `tdm_archive`, em vez de consultar a tabela removida.
  A quantidade de tabelas reportada vem dos modelos atuais. A opcao `--export-sql`
  permite executar as mesmas protecoes pelo SQL Editor ou API administrativa.
- O comando conectado de auditoria agora informa `missing_product_stock`, para
  detectar a falta de estoque mesmo quando as tabelas e migrations estao corretas.

Para exportar a verificacao das protecoes sem precisar de uma conexao TCP:

```bash
python scripts/verify_supabase_integrity.py --export-sql /tmp/supabase-integrity.sql
```

O SQL insere apenas em tabelas temporarias, usa IDs explicitos e as remove ao
terminar a transacao. A exportacao da auditoria de estrutura continua disponivel
com `scripts/audit_supabase.py --export-sql`.

Os advisors de seguranca e desempenho retornaram somente o aviso de protecao
contra senhas vazadas do Supabase Auth. A autenticacao ativa da loja e propria
do FastAPI; nenhuma configuracao do Supabase Auth foi alterada.

O acesso pela CLI da Vercel funcionou. As buscas de logs nao retornaram erros
recentes no intervalo consultado, o que nao comprova uma compra ou consulta
publicada bem-sucedida. A falha `EAUTHQUERY` do relatorio de 26/10 continua sendo
evidencia historica. O acesso PostgreSQL direto desta rede segue sem validacao;
nao houve reset de senha, reinicio do banco ou troca de endpoint por tentativa.

As correcoes de codigo permanecem locais. Nenhuma variavel de producao foi
alterada e nenhum deploy foi realizado. Os 115 testes locais passaram. A validacao cobre selecao de pool,
timeout enviado ao driver, erros sem exposicao de credenciais e deteccao de estoque
ausente; os resultados dos testes e das consultas remotas foram conferidos.

Referencias: [conexoes Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres),
[pooling SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/core/pooling.html),
[timeout libpq](https://www.postgresql.org/docs/17/libpq-connect.html#LIBPQ-CONNECT-CONNECT-TIMEOUT).
