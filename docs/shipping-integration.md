# Melhor Envio e BrasilAPI

Integração da API ativa do FastAPI, carrinho e Stripe Checkout. O frete é cotado
pelo backend com preços, pesos e dimensões dos produtos cadastrados. O navegador
envia o ID da cotação e o serviço escolhido; não define o valor do frete.

Referências oficiais:
- [Fluxo completo Melhor Envio](https://docs.melhorenvio.com.br/docs/fluxo-completo-de-integracao)
- [Cotação e preços personalizados](https://docs.melhorenvio.com.br/reference/calculo-de-fretes-por-produtos)
- [Inserção, volumes e NF-e](https://docs.melhorenvio.com.br/reference/inserir-fretes-no-carrinho)
- [Autorização OAuth](https://docs.melhorenvio.com.br/reference/fluxo-de-autoriza%C3%A7%C3%A3o)
- [Tokens e renovação](https://docs.melhorenvio.com.br/reference/solicitacao-do-token)
- [Pagamento das etiquetas](https://docs.melhorenvio.com.br/reference/compra-de-fretes-1)
- [Geração](https://docs.melhorenvio.com.br/reference/geracao-de-etiquetas)
- [Impressão](https://docs.melhorenvio.com.br/reference/impressao-de-etiquetas)
- [Status](https://docs.melhorenvio.com.br/reference/rastreio-de-envios)
- [BrasilAPI e termos de uso](https://brasilapi.com.br/docs#tag/Termos-de-uso)
- [Orientação de consultas sob demanda](https://github.com/BrasilAPI/BrasilAPI#termos-de-uso)

## Ativação no Sandbox

1. Aplique a migração `supabase/migrations/20260914163703_melhor_envio_shipping.sql`
   pelo fluxo de migrations do projeto. Ela adiciona medidas aos produtos e cria
   tabelas de conexão, cotação e envio. Não foi aplicada automaticamente no banco
   remoto durante o desenvolvimento. Reinicie o backend após aplicá-la; a criação
   de tabelas no startup não adiciona colunas em tabelas existentes.
2. Cadastre um aplicativo na Área Dev do Melhor Envio Sandbox. O callback
   cadastrado deve ser **idêntico** ao `MELHOR_ENVIO_REDIRECT_URI` do backend.
3. Configure exclusivamente no `.env` do backend:

   ```dotenv
   MELHOR_ENVIO_ENVIRONMENT=sandbox
   MELHOR_ENVIO_CLIENT_ID=
   MELHOR_ENVIO_CLIENT_SECRET=
   MELHOR_ENVIO_REDIRECT_URI=http://localhost:8000/api/v1/shipping/oauth/callback
   MELHOR_ENVIO_USER_AGENT=
   MELHOR_ENVIO_SENDER={}
   MELHOR_ENVIO_SERVICES=1,2,3,4
   MELHOR_ENVIO_FREE_SHIPPING_THRESHOLD=150
   FRONTEND_URL=http://localhost:5173
   ```

   Preencha o User-Agent com `Toque de Mulher (seu-email-de-contato)`.
   `FRONTEND_URL` deve usar a porta real do frontend; configure também os retornos
   Stripe e `CORS_ORIGINS`. Não use variáveis `VITE_` para as credenciais.

   `MELHOR_ENVIO_SENDER` é um JSON em uma única linha com os dados reais da loja:

   ```json
   {"name":"","email":"","phone":"","company_document":"","state_register":"","address":"","number":"","complement":"","district":"","city":"","postal_code":"","state_abbr":""}
   ```

   CEP: oito dígitos; telefone: DDD e número; documento da empresa: CNPJ;
   inscrição estadual: a informação real da loja, inclusive `ISENTO` se aplicável.
4. Entre com uma conta administradora e acesse **Envios e etiquetas**
   (`/admin/envios`). Clique em **Conectar conta** e autorize o aplicativo.
   Use o mesmo hostname no frontend e no backend (`localhost` em ambos, por
   exemplo). A autorização verifica cookie HttpOnly, estado aleatório de dez
   minutos e uso único. Em produção, o callback deve usar HTTPS.
5. No mesmo painel, selecione cada produto e informe as medidas unitárias do
   produto embalado em centímetros e o peso em quilogramas. Produtos sem medidas
   ou ausentes/inativos no banco não podem ser cotados. O catálogo atual do
   frontend utiliza dados locais: os itens precisam corresponder aos produtos
   reais cadastrados (UUID, slug ou nome), como já ocorre no checkout Stripe.

## Fluxo do cliente

1. No carrinho, informe o CEP, consulte as transportadoras e selecione a entrega.
2. A cotação utiliza `custom_price` e `custom_delivery_range`, excluindo serviços
   indisponíveis. O preço e prazo continuam vinculados à cotação no backend.
3. A opção mais econômica recebe frete grátis acima do limite configurado;
   serviços expressos continuam mostrando o próprio preço. `0` desativa o benefício.
4. O checkout consulta o CEP pela BrasilAPI v2 ao sair do campo completo e permite
   preenchimento manual. No cadastro de endereços, a mesma API substitui o ViaCEP.
5. Na etapa de pagamento, confirme a entrega, nome, e-mail, telefone completo e CPF
   do destinatário. CPF é validado no backend; esses dados ficam no snapshot do envio.
6. A Stripe recebe produtos com seus preços reais e uma linha de frete quando há
   cobrança. O pagamento registrado inclui esse frete. Endereço alterado, cotação
   expirada, serviço fora da cotação ou mudança nos produtos exige nova cotação.
   Alterações em itens, quantidade ou preço invalidam a seleção no navegador.
7. O perfil apresenta serviço, prazo após postagem, status e códigos de rastreio.
   O cliente só pode consultar seus próprios pedidos.

O antigo cupom aplicado apenas no navegador foi removido do carrinho porque o
checkout não o validava nem cobrava o valor com desconto. Não há frete fictício
como fallback quando o provedor está indisponível.

## Fluxo administrativo

1. Aguarde o webhook Stripe confirmar o pagamento do pedido.
2. Informe a chave de NF-e (44 dígitos) e clique em **Preparar etiquetas**.
   O envio comercial usa `non_commercial=false`; não substitui NF-e por declaração.
   O cadastro utiliza remetente e destinatário salvos, produtos declarados e os
   pacotes retornados pela cotação.
3. Clique em **Pagar ... da carteira**. Essa ação compra o frete usando o saldo da
   conta Melhor Envio. O pagamento da etiqueta é distinto do pagamento Stripe do
   cliente; é necessário saldo na carteira do ambiente escolhido.
4. Clique em **Gerar etiquetas**. A geração é assíncrona.
5. Consulte o status até aparecer **Pronto para postagem** e clique em
   **Obter impressão**. O link é privado: abra com a conta Melhor Envio conectada
   no navegador. Após imprimir, poste o pacote conforme o serviço escolhido.
6. Consulte o status para acompanhar postagem e entrega. Foi implementada busca
   ativa; não é necessário configurar um webhook Melhor Envio nesta versão.

Correios, J&T e Loggi recebem uma chamada ao carrinho por pacote; transportadoras
que aceitam múltiplos volumes recebem todos em uma chamada. Serviços padrão são
Correios e Jadlog (`1,2,3,4`); confira exigências de agência/XML antes de habilitar
outros serviços no ambiente real. Esta implementação exige NF-e para a loja e
não implementa envios não comerciais/DC-e, logística reversa ou recarga da carteira.

Se uma criação ou compra for interrompida, ela fica em **Conferência necessária**.
Não há repetição automática de operações financeiras. Consulte o status das
etiquetas antes de repetir; para criação interrompida, confira a conta Melhor
Envio e informe todos os IDs em **Recuperar criação interrompida**. A integração
verifica a tag do pedido, o serviço e o CEP antes de aceitar os IDs.

## Operação e segurança

- Tokens são cifrados com Fernet usando chave derivada de `SECRET_KEY` do backend.
  São renovados sob demanda cinco minutos antes da expiração. Rotacionar
  `SECRET_KEY` exige reconectar a conta. Sandbox e produção têm conexões separadas.
- As três tabelas possuem RLS e não dão acesso aos papéis da Data API Supabase.
  Use a conexão SQL do backend com privilégios próprios para essas tabelas.
- Cotações públicas validam entradas e resolvem preços no banco. IDs não permitem
  consultar pedidos de outros usuários. Somente administradores operam etiquetas.
- BrasilAPI é usada apenas sob demanda, sem varredura de dados. O backend mantém
  cache de CEPs por 24 horas, com no máximo 512 entradas, timeout de cinco segundos
  e limite de 30 consultas por minuto por cliente/categoria. Esse limite é local
  à aplicação, não representa uma cota contratada com o provedor. Em instalações
  com múltiplos workers, configure limite compartilhado no proxy/API gateway.
- Operações do Melhor Envio têm timeout de dez segundos e não usam fallback de
  preço inventado. Configure `MELHOR_ENVIO_USER_AGENT` conforme a documentação.
- Cotações têm validade de 15 minutos. Envios mantêm o snapshot comprado; não
  delete cotações vinculadas a pedidos. Cotações expiradas sem envios podem ser
  removidas pela rotina de manutenção do banco.
- Em produção, use app e credenciais de produção após validar Sandbox. Confira
  cadastro, NF-e, saldo e serviços da conta. Nenhuma compra real foi realizada
  durante a implementação.

## Validação

```bash
.venv/bin/python -m pytest tests/ -q
```

Os testes usam banco SQLite isolado e exemplos oficiais de resposta do Melhor
Envio. Cobrem validação do frete antes de cobrar, valor total, isolamento por
usuário, permissões administrativas, fluxo de etiquetas, geração assíncrona,
interrupção sem repetição, OAuth, renovação, cache, erros e limite da BrasilAPI.
A migração também foi executada em PostgreSQL temporário durante desenvolvimento,
sem acesso ao banco real. Complete a homologação com a própria conta Sandbox
antes de habilitar produção.
