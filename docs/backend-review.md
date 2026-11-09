`

# Revisao do backend — 09/11/2026

Foram reproduzidas e corrigidas falhas de identidade dos tokens, recuperacao de
senha, confirmacao de email, upload de avatar e validacao de precos. As operacoes
administrativas de estoque tambem passaram a bloquear e recarregar os saldos
antes de altera-los.

| Cenario                                               | Comportamento corrigido                                                                                                                                    |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Email alterado e depois registrado por outra pessoa   | O token continua ligado ao UUID da conta original. O email deixou de identificar a sessao.                                                                 |
| Senha alterada ou redefinida                          | Tokens de acesso anteriores sao recusados, usando uma assinatura HMAC da versao da senha. O hash da senha nao e incluido no JWT.                           |
| Link de redefinicao repetido                          | O link exige UUID, email atual e versao da senha. A conta e bloqueada durante a validacao/alteracao para impedir reutilizacao concorrente.                 |
| Link de confirmacao antigo apos reutilizacao do email | O link exige o UUID original e o email atual; nao confirma a conta de outra pessoa.                                                                        |
| Troca de email confirmado                             | A confirmacao anterior e removida e um novo link e enviado ao novo endereco.                                                                               |
| Upload de avatar em ambiente sem disco persistente    | O arquivo passa pelo Supabase Storage, na pasta `avatars/<UUID>/` do bucket de imagens configurado. O perfil recebe uma URL HTTPS.                       |
| Arquivo vazio, grande demais ou Storage indisponivel  | Retorna 400, 413 ou 503; o perfil nao recebe uma URL de upload que falhou. Falha HTTP do provedor retorna 502.                                             |
| Preco negativo, NaN ou infinito                       | O pedido e rejeitado com 422 antes da persistencia. Erros com valores nao finitos tambem produzem JSON valido.                                             |
| Entrada, ajuste, zeramento ou liberacao de estoque    | O saldo e bloqueado e recarregado; entradas de varios produtos seguem a ordem de UUID usada pelo checkout. Uma entrada invalida e revertida integralmente. |

## Compatibilidade ao publicar

Usuarios precisam entrar novamente depois da publicacao: os tokens anteriores
nao possuem o UUID e a versao da senha exigidos. Links antigos de redefinicao
e confirmacao tambem devem ser substituidos por novos links.

`POST /api/v1/user/resend-confirmation` recebe `{"email":"cliente@example.com"}`
e responde com a mesma mensagem para emails existentes e inexistentes. O envio
ocorre apenas para contas ativas ainda nao confirmadas. Esse endpoint e o de
recuperacao de senha usam o limitador existente, com 30 pedidos por cliente/minuto
por processo. O limite nao e distribuido entre instancias.

O avatar usa `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_BUCKET` e o
limite `PRODUCT_IMAGE_MAX_BYTES`, cujo padrao e 5 MB. A chave continua exclusiva
do backend. Avatares antigos em `/static/uploads/avatars/` nao foram migrados;
o usuario pode enviar uma nova foto. O frontend ja aceita URLs HTTPS absolutas.

## Verificacao e limites

Resultado da suite completa: **135 testes passaram**, incluindo 20 casos novos
de regressao. `git diff --check` e a compilacao dos arquivos Python passaram.
Permanece o aviso de depreciacao de `crypt` em uma dependencia existente.

Os testes de regressao cobrem as falhas reproduzidas, a troca/reutilizacao de
email, revogacao de sessao, recuperacao e reenvio de confirmacao, transporte de
arquivo, limite de tamanho, timeout do Storage, valores nao finitos e atomicidade
de entradas de estoque. A atualizacao de um saldo carregado em uma sessao antiga
tambem foi verificada.

`tests/conftest.py` isola o SQLite, desativa SMTP e configura chaves Stripe de
teste antes de importar as configuracoes da aplicacao, inclusive quando se roda
um arquivo de testes separadamente. Os testes de upload usam transporte HTTP
simulado. `pip check` nao encontrou dependencias quebradas.

Os testes de API usam SQLite; concorrencia entre processos em PostgreSQL nao foi
homologada nesta revisao. As clausulas de bloqueio foram conferidas no dialeto
PostgreSQL. Stripe, Melhor Envio e o envio real de email ainda dependem da
homologacao e configuracao externas descritas em `storefront-review.md`.

Estas alteracoes permanecem locais; nenhum deploy ou mudanca de variavel de
producao foi realizado nesta revisao do backend.
