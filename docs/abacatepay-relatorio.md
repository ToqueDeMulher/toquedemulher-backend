# Relatório da migração de pagamentos

**Status da entrega local — APROVADO COM RESSALVAS.** A liberação em produção
depende da homologação com a AbacatePay. O backend e o frontend estão na
branch `feat/abacatepay-migration` de seus respectivos repositórios.

## O que entrou

- Pix transparente com QR Code, código copia e cola, validade de 15 minutos,
  consulta de status e recuperação de tentativa.
- Cartão de crédito no checkout hospedado da AbacatePay, com seleção na loja
  quando `ABACATEPAY_CARD_ENABLED=true` e cartão habilitado no provedor.
- Total calculado a partir do catálogo e do frete verificado. Reserva, itens
  e remessa são persistidos antes da emissão. Timeout no Pix reutiliza a
  referência. Timeout no cartão concilia o checkout existente pelo pedido.
- Consulta autenticada no provedor, webhook v2, devolução de reserva quando
  expiração, falha ou cancelamento são confirmados, e conciliação periódica
  de pedidos abandonados. O cliente pode verificar o estado e retomar o
  pagamento. Cancelamentos AbacatePay são refletidos quando o provedor os
  reporta. Estornos integrais são iniciados no painel do provedor.
- Confirmação do pagamento libera o fluxo de envio. Reembolso em análise,
  disputa e pagamento Dev Mode com frete de produção bloqueiam essa liberação.
- Stripe permanece disponível para o histórico, o webhook de cobranças
  antigas e rollback. **Dependências Stripe removidas — nenhuma.**
  A migration é aditiva e o guia descreve quando retirar o legado.

## Auditoria de segurança

A skill `security-audit` foi aplicada em revisão estática do fluxo de
pagamentos, com uma análise independente do código anterior e uma verificação
independente da migração. O escopo abrangeu preços, autenticação, autorização,
persistência, webhooks, estoque e envio. O daemon Docker indisponível impediu
a execução isolada da auditoria dinâmica. A suíte funcional rodou em uma
cópia local sem o arquivo de ambiente e com dados de teste.

| Achado | Correção |
| --- | --- |
| Busca do webhook Stripe por metadata permitia atingir pagamentos de outro provedor e aprovar sem comparar valor e moeda | Filtragem por provedor e ID externo. Aprovação e reembolso integral exigem comparação de valor e moeda |
| Uma conta podia manter várias reservas simultâneas, e cobranças abandonadas dependiam de retorno ou webhook | Um pagamento AbacatePay pendente por conta, bloqueio de linha e tarefa periódica com rotação mesmo após falhas |
| Consulta repetida podia consumir recursos do gateway e atrasar a conciliação | Resultado de consulta reutilizado no servidor por seis segundos por cobrança. Tentativas de consulta sem sucesso também ficam registradas |
| Segredo do webhook chega na query e podia entrar no access log. Exceções completas podiam trazer dados do pedido | Access log Uvicorn desabilitado no contêiner e no comando documentado. Logs do checkout registram IDs internos e tipo de erro. Sanitização do ingress permanece uma etapa do deploy |
| HMAC da AbacatePay usa chave pública | Segredo privado conferido em tempo constante, HMAC sobre corpo bruto limitado a 64 KiB e consulta autenticada da cobrança antes da aprovação |
| Falhas ou eventos repetidos podiam disputar a reserva ou repetir a emissão | Intenção persistida antes da chamada, referência estável para Pix, cartão ambíguo conciliado antes de qualquer ação, estado terminal e devolução de estoque protegidos por bloqueio de linha |
| Um estorno autêntico podia chegar enquanto o provedor ainda retornava `PAID`, e a etiqueta podia usar status antigo | Bloqueio imediato do envio enquanto o estorno é confirmado. A preparação e a compra da etiqueta atualizam e bloqueiam o pagamento antes de registrar a operação |
| Pagamento Dev Mode podia liberar etiqueta real por configuração cruzada | Guardas de ambiente no checkout e nas operações financeiras de envio |

A auditoria cobriu também a propriedade do pedido, o uso de consultas
parametrizadas, a restrição da URL de cartão à origem do provedor e a validação
da imagem PNG do Pix. O backend usa a moeda BRL, o valor em centavos, o
identificador externo e o ambiente para conciliar. A lista oficial de eventos,
os formatos e os métodos de autenticação estão na documentação.
[Webhooks AbacatePay](https://docs.abacatepay.com/pages/webhooks/security)

## Validação e pendências

- **146 testes de backend passaram** com SQLite e respostas simuladas da
  AbacatePay. Testes de emissão,
  dados inválidos, preço adulterado, acesso entre contas, QR Code, timeout,
  indisponibilidade, webhook inválido, duplicado e fora de ordem, aprovação,
  estorno, expiração, cancelamento, recusa e autorização de envio.
- **42 testes de navegador passaram** no Chromium em desktop e celular com
  API simulada. Testes de Pix do
  carrinho até a confirmação, cartão hospedado com retorno, feedback de erro
  e preservação do carrinho até aprovação.
- Migration aplicada duas vezes em PostgreSQL embutido. Pagamentos Stripe
  pendente e reembolsado, vínculos de itens e RLS preservados. A unicidade do
  identificador de cobrança AbacatePay foi verificada.
- Typecheck TypeScript, build Vite e compilação Python passaram. O Ruff passou
  nos módulos centrais de pagamento verificados. A checagem global do backend
  passou de 481 para 458 apontamentos e continua pendente. O frontend dispõe
  de typecheck e build, sem script de lint.
- `pip-audit` e `npm audit` retornaram zero vulnerabilidades conhecidas nas
  dependências verificadas. O build Docker ficou bloqueado pelo daemon
  indisponível.
- Falta validar a criação, simulação, estorno, cartão habilitado e entrega de
  webhooks em uma loja **Dev Mode**. Falta testar concorrência com PostgreSQL
  servido ao backend e fazer o inventário financeiro Stripe com acesso
  autorizado. Os testes de navegador e API simulada foram separados. A
  execução usou apenas cobranças e dados de teste.
- A lista de variáveis, permissões, agendamento, etapas de homologação e
  plano de corte está no [guia de operação](abacatepay.md).

## Arquivos

**Backend criados**

- `app/api/v1/endpoints/abacatepay_webhook.py`
- `app/services/abacatepay.py`
- `scripts/reconcile_abacatepay.py`
- `supabase/migrations/20261109140000_abacatepay_payments.sql`
- `tests/test_abacatepay.py`
- `docs/abacatepay.md` e `docs/abacatepay-relatorio.md`

**Backend movido e atualizado**

- `app/api/v1/endpoints/stripeCheckout.py` foi substituído por
  `app/api/v1/endpoints/payments.py`, que mantém as rotas HTTP existentes.

**Backend modificados**

- `.dockerignore`, `.env.example`, `Dockerfile`, `README.md`
- `app/api/v1/router.py`, `app/api/v1/endpoints/admin.py`,
  `app/api/v1/endpoints/shipping.py`, `app/api/v1/endpoints/weebhook.py`
- `app/core/settings.py`, `app/models/payment.py`,
  `app/schemas/create_checkout.py`, `app/services/shipment_service.py`
- `docs/integration-setup.md`, `docs/shipping-integration.md`
- `tests/conftest.py`, `tests/test_auth.py`, `tests/test_shipping.py`,
  `tests/test_storefront.py`

**Frontend modificados**

- `src/app/layout/components/PageNavigation.tsx`
- `src/features/auth/pages/ProfilePage.tsx`
- `src/features/cart/api/checkout-service.ts`
- `src/features/cart/pages/CheckoutPage.tsx` e `CheckoutPage.module.css`
- `src/features/institutional/pages/HelpPage.tsx` e `InstitutionalPage.tsx`
- `tests/browser/storefront.spec.ts`

**Skills aplicadas**

`security-audit` na revisão independente de confiança e autorização,
`fastapi-expert` no contrato da API e nas dependências de autenticação,
`react-expert` e `typescript-pro` no checkout e nos estados tipados,
`design-taste-frontend` na revisão visual com o design existente,
`test-master` nos testes de integração e navegador, e `debugging-wizard`
na reprodução e correção das falhas de teste.
