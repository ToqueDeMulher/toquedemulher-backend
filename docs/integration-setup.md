# Integrações — 09/11/2026

O ambiente solicitado é de **teste**: Stripe test e Melhor Envio sandbox.
O nome `Production` abaixo é o ambiente de publicação da Vercel; não significa
que pagamentos ou etiquetas reais estejam liberados.

## Configuração do backend

Foram salvas no projeto `toquedemulher-backend`, em `Production`:

| Variável | Valor |
| --- | --- |
| `FRONTEND_URL` | `https://toquedemulher-frontend.vercel.app` |
| `FRONTEND_SUCCESS_URL` | `https://toquedemulher-frontend.vercel.app/checkout/success` |
| `FRONTEND_PENDING_URL` | `https://toquedemulher-frontend.vercel.app/checkout/pending` |
| `FRONTEND_FAILURE_URL` | `https://toquedemulher-frontend.vercel.app/checkout/failure` |
| `CONTACT_RECIPIENT_EMAIL` | Endereço informado pela loja, salvo na Vercel |
| `MELHOR_ENVIO_ENVIRONMENT` | `sandbox` |
| `MELHOR_ENVIO_REDIRECT_URI` | `https://toquedemulher-backend.vercel.app/api/v1/shipping/oauth/callback` |

As variáveis passam a valer em uma nova publicação. O endereço destinatário de
contato não foi configurado como `STORE_CONTACT_EMAIL`, que publica o endereço
na API da loja. SMTP já possuía configuração; a entrega real de mensagens ainda
precisa ser homologada.

## Pendências confirmadas pela loja

A loja ainda não possui as credenciais Stripe e Melhor Envio, nem os dados reais
de estoque e embalagem. Pagamentos, frete e cadastro permanecem pendentes.
Os saldos existentes foram preservados e continuam zerados nos quatro produtos
ativos. Nenhum produto foi liberado para venda nesta correção.

O arquivo [catalogue-pending.csv](catalogue-pending.csv) lista os quatro produtos
e os campos a confirmar. A coluna `current_stock` é o saldo observado, não uma
contagem física confirmada. Campos em branco devem ser preenchidos com dados
reais. `Teste 1` também está sem imagem. O arquivo serve para revisão e não é
importado automaticamente. Não foram inventadas categorias, medidas ou saldos.

## Quando as credenciais estiverem disponíveis

1. No Stripe, usar o modo de teste e salvar `STRIPE_SECRET_KEY` de teste como
   segredo no backend da Vercel. Nunca usar uma chave `sk_live_` nesta homologação.
2. Criar um webhook de teste para
   `https://toquedemulher-backend.vercel.app/api/v1/payments/webhook`, com os eventos
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `checkout.session.async_payment_failed`, `checkout.session.expired` e
   `charge.refunded`. Salvar o segredo desse endpoint em `STRIPE_WEBHOOK_SECRET`.
3. Criar o aplicativo no Melhor Envio sandbox e cadastrar exatamente a URL de
   callback da tabela acima. Salvar `MELHOR_ENVIO_CLIENT_ID` e
   `MELHOR_ENVIO_CLIENT_SECRET` como segredos no backend da Vercel.
4. Publicar novamente o backend e conectar o Melhor Envio na área administrativa,
   em `/admin/envios`. Configurar as medidas reais das unidades embaladas nessa
   mesma área. Conferir os dados reais de remetente em `MELHOR_ENVIO_SENDER`.
5. Confirmar categorias e estoque com a loja antes de disponibilizar produtos.
6. Homologar confirmação/recuperação de e-mail, contato, cotação, checkout de teste,
   assinatura e repetição do webhook. Nenhum destes passos exige cobrança ou
   compra de etiqueta em produção.

## Correções de código e validação

- Dependências Python e npm atualizadas para corrigir os avisos conhecidos.
  As auditorias locais `pip-audit` e `npm audit` retornaram zero vulnerabilidades
  conhecidas em 09/11/2026. Isso não é uma garantia sobre avisos futuros.
- React Router atualizado para 7.18.5, mantendo React 18. Vite continua na linha 7.
- Confirmação de e-mail permite solicitar outro link quando o anterior está
  ausente, inválido ou expirado. Falhas preservam o e-mail e permitem repetir.
- Redefinição de senha exibe o campo `mensagem` retornado pelo backend.
- Troca de senha encerra a sessão após sucesso e solicita novo login. Falhas
  preservam a sessão; o carrinho é preservado nos dois casos.
- Backend: 135 testes passaram após a atualização das dependências.
- Frontend: verificação TypeScript e build passaram; os testes de navegador
  exercitam desktop e celular, com respostas de API simuladas.

Nenhum e-mail real foi enviado, nenhuma cobrança foi criada e nenhuma etiqueta
foi comprada nesta execução. Os testes locais não substituem a homologação com
as credenciais dos provedores.
