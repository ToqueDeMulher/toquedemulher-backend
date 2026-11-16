# Pagamentos pela AbacatePay

A loja vende produtos físicos em pedidos avulsos. O total do pedido combina
preços do catálogo com o frete validado pelo backend. O Pix expira em 15 minutos
e apresenta QR Code e código copia e cola no checkout. O cartão abre a página
da AbacatePay. O backend confirma o pagamento antes de permitir a preparação ou
o pagamento da etiqueta no Melhor Envio.

## Configuração de homologação

Use um banco PostgreSQL descartável e uma loja AbacatePay no **Dev Mode**.
Aplique a migration `supabase/migrations/20261109140000_abacatepay_payments.sql`
antes de publicar o código que lê as novas colunas de `payment`.

| Variável no backend | Valor ou finalidade |
| --- | --- |
| `PAYMENT_PROVIDER` | `abacatepay` para novos checkouts |
| `ABACATEPAY_API_KEY` | Chave privada de **Dev Mode** com `TRANSPARENT:CREATE` e `TRANSPARENT:READ` para Pix. Para cartão, inclua `CHECKOUT:CREATE`, `CHECKOUT:READ`, `PRODUCT:CREATE` e `PRODUCT:READ` |
| `ABACATEPAY_WEBHOOK_SECRET` | Mesmo segredo aleatório definido ao cadastrar o webhook |
| `ABACATEPAY_DEV_MODE` | `true` durante toda a homologação |
| `ABACATEPAY_CARD_ENABLED` | `true` quando o cartão estiver disponível na loja da AbacatePay |
| `FRONTEND_SUCCESS_URL` | URL HTTPS da loja terminada em `/checkout/success` |
| `FRONTEND_PENDING_URL` | URL HTTPS da loja terminada em `/checkout/pending` |

As credenciais ficam no backend. O frontend descobre os métodos disponíveis
pela API e usa a configuração habitual de `VITE_API_URL`.

1. Cadastre o webhook HTTPS público em
   `/api/v1/payments/webhooks/abacatepay`. Selecione `transparent.completed`,
   `transparent.refunded`, `transparent.disputed`, `transparent.lost` e, com
   cartão, os eventos `checkout.completed`, `checkout.refunded`,
   `checkout.disputed` e `checkout.lost`.
2. Configure ingress, proxy, hospedagem e observabilidade para excluir a query
   desse endpoint de logs e traces. A AbacatePay envia o segredo no parâmetro
   `webhookSecret`. O Uvicorn do Docker inicia com o access log desativado.
3. Execute `python -m scripts.reconcile_abacatepay --limit 100` a cada minuto
   no ambiente do backend. Evite execuções sobrepostas e monitore o código de
   saída. Ajuste o limite à fila. A tarefa busca cobranças pendentes, em disputa ou com
   reembolso em análise, libera reservas expiradas e registra pedidos que precisam de revisão.
4. Com o frete em sandbox, faça um pedido Pix, veja o código na loja e confirme
   que o pedido permanece pendente. Use o ID `pix_char_…` desse pedido no
   [simulador do Dev Mode](https://docs.abacatepay.com/pages/transparents/simulate-payment).
   Verifique a entrega do webhook, a atualização do pedido e a liberação do envio.
5. Faça um segundo Pix e deixe expirar para verificar a devolução da reserva.
   Faça um checkout de cartão com os dados de teste autorizados pela AbacatePay
   e verifique o redirecionamento, o valor pago, o webhook e o retorno à loja.
   Homologue também uma recusa e um estorno integral de teste para cada método.

A conciliação usa leitura autenticada do provedor e compara ID, valor em
centavos, moeda e ambiente. A API v2 opera em BRL e pode omitir o campo de
moeda. O webhook valida o segredo de origem e o HMAC do corpo bruto antes de
consultar a cobrança. Estado e estoque são atualizados juntos sob bloqueio de
linha no PostgreSQL. A consulta do cliente reutiliza o resultado por seis
segundos. O QR Code é mantido no banco apenas enquanto estiver pendente.
Um evento autêntico de reembolso coloca o pedido em espera até a conciliação.
Pagamentos Dev Mode exigem frete em sandbox.

## Operação e exceções

- A mesma tentativa Pix usa o ID do pedido como `externalId`. Em caso de
  timeout, procure a cobrança existente antes de tentar emitir novamente. A
  reserva e os itens ficam registrados mesmo quando o retorno da API se perde.
- O cartão usa um produto técnico por total em BRL, obtido ou criado pelo
  backend. O checkout hospedado é emitido uma única vez por tentativa. Se a
  resposta se perder, o reconciliador procura o checkout pelo `externalId`.
  Se o provedor continuar sem retornar o checkout, encaminhe para revisão
  operacional. Confirme no painel ou com o suporte antes de encerrar a reserva.
  A mesma revisão vale para emissão Pix que permaneça sem registro após um
  erro de resposta ambíguo.
- O botão para acompanhar um pedido pendente recupera o pedido da conta após
  uma queda de conexão. A loja mantém uma cobrança AbacatePay pendente por
  conta. Apenas um estado terminal confirmado libera a reserva de uma cobrança
  que pode ter sido emitida. Para pedidos cuja emissão sequer iniciou, a
  conciliação pode encerrar a reserva após 15 minutos.
- O Pix expira no provedor. Para o cartão, a loja concilia os estados finais
  que o checkout hospedado reporta. Uma recusa que mantenha o checkout aberto
  pode ser tratada no próprio checkout. O cliente não cancela uma cobrança
  AbacatePay pelo retorno à loja.
- Faça reembolsos integrais no painel do provedor. O backend concilia o status
  do reembolso e preserva o histórico. Revise o estoque de acordo com o
  retorno físico da mercadoria. A disputa no cartão bloqueia o envio e requer
  revisão operacional caso o checkout continue reportando `PAID`.
- Identifique os logs de pedidos sem confirmação de emissão e falhas de
  conciliação. Esses alertas exigem acompanhamento da loja. Se um pagamento aparecer após
  a liberação da reserva, o webhook pede reentrega e registra o pedido para
  conciliação manual. Verifique a disponibilidade ou encaminhe o reembolso
  pelo provedor antes de movimentar o estoque.

## Transição do Stripe

1. Antes do corte, inventarie pagamentos Stripe por estado no banco e compare
   os pendentes, estornos e eventuais disputas com o painel do provedor. Uma
   consulta de leitura para começar:

   ```sql
   SELECT status, count(*)
   FROM public.payment
   WHERE provider = 'stripe'
   GROUP BY status
   ORDER BY status;
   ```

2. Preserve linhas de pagamentos, itens, estoque e remessas. A migration
   acrescenta colunas e índices e conserva os vínculos antigos.
3. Preserve as variáveis `STRIPE_SECRET_KEY` e `STRIPE_WEBHOOK_SECRET` e o
   endpoint `/api/v1/payments/webhook` enquanto existirem cobranças antigas
   que possam receber confirmação, expiração ou reembolso. Complete a
   conciliação antes de repetir uma compra que já esteja pendente no Stripe.
4. Após homologar Pix e cartão em Dev Mode e aplicar a migration com
   autorização, configure a chave de produção, o segredo e o webhook do
   ambiente de produção e mude `ABACATEPAY_DEV_MODE` para `false`.
   Mantenha o job de conciliação no mesmo ambiente das cobranças que ele lê.
5. Para rollback operacional, `PAYMENT_PROVIDER=stripe` volta a emitir novas
   cobranças no Stripe. Mantenha o webhook, as credenciais e o reconciliador
   AbacatePay ativos até concluir seus pedidos abertos. Se o frontend estiver
   em cache, atualize a etapa de pagamento antes de emitir outra cobrança.
6. Após encerrar a janela de retorno e conciliar o legado, retire as
   credenciais e o código de emissão, consulta e webhook Stripe em uma mudança
   separada. Os registros financeiros continuam acessíveis no histórico.

Referências oficiais da AbacatePay [Pix transparente](https://docs.abacatepay.com/pages/transparents/create),
[checkout hospedado](https://docs.abacatepay.com/pages/payment/create),
[status do checkout](https://docs.abacatepay.com/pages/payment/one),
[reembolsos Pix](https://docs.abacatepay.com/pages/transparents/refund),
[webhooks](https://docs.abacatepay.com/pages/webhooks/security)
e [Dev Mode](https://docs.abacatepay.com/pages/devmode).
