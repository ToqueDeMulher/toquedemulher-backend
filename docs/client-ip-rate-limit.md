# IP do cliente e limite de consultas

O backend limita a 30 requisições por minuto, por cliente e por categoria, as
rotas que chamam serviços externos ou enviam e-mail: cotação de frete
(`quotes`), consulta de CEP (`cep`), sincronização de rastreio (`tracking`),
contato, confirmação de e-mail e redefinição de senha. O limite fica em
`app/services/brasil_api.py` (`check_rate_limit`).

## Regra de confiança

A aplicação **nunca lê `X-Forwarded-For`, `X-Real-IP` ou `X-Vercel-Forwarded-For`**.
Ela usa só `request.client.host`, o endereço que o servidor ASGI (Uvicorn)
resolveu. O Uvicorn troca o endereço da conexão pelo valor de `X-Forwarded-For`
apenas quando a conexão vem de um IP listado em `FORWARDED_ALLOW_IPS` (padrão
`127.0.0.1`) e, mesmo assim, usa a entrada mais à direita que não seja de um
proxy confiável. Assim:

- um cliente que envia `X-Forwarded-For` falso diretamente ao backend continua
  sendo identificado pelo IP da conexão;
- entradas forjadas à esquerda do cabeçalho não mudam o grupo do cliente;
- IPv6 é agrupado por prefixo `/64`, que normalmente pertence a um único
  assinante;
- a memória do limitador guarda resumos (BLAKE2b com chave aleatória por
  processo), não IPs. Nenhum IP é registrado em log.

## Docker (imagem do GHCR)

O `Dockerfile` executa `uvicorn` diretamente.

| Situação | `FORWARDED_ALLOW_IPS` |
| --- | --- |
| Porta 8000 exposta diretamente, sem proxy | não definir |
| nginx/Traefik no mesmo host | IP do proxy, por exemplo `127.0.0.1` |
| Proxy em outro contêiner da rede Docker | faixa da rede, por exemplo `172.18.0.0/16` (`docker network inspect`) |
| Load balancer gerenciado | faixa privada informada pelo provedor |

Nunca use `*` se a porta 8000 puder ser acessada sem passar pelo proxy: qualquer
pessoa poderia escolher o próprio IP. O proxy deve **substituir** (não apenas
acrescentar) o cabeçalho, por exemplo no nginx:
`proxy_set_header X-Forwarded-For $remote_addr;`.

## Vercel

Na Vercel o `Dockerfile` não é usado e **`FORWARDED_ALLOW_IPS` não deve ser
definida**. O runtime Python (`vercel-runtime`, `vc_init.py`) inicia um Uvicorn
próprio em `127.0.0.1` e repassa a ele os cabeçalhos da borda da Vercel. Como a
conexão vem de `127.0.0.1`, o Uvicorn usa o `X-Forwarded-For` que a borda
definiu. A Vercel sobrescreve esse cabeçalho com o IP de quem se conectou a ela,
então o cliente não consegue falsificá-lo.

### Chamadas pelo proxy do frontend (`vercel.json`)

Em produção o frontend chama `/api/...` no próprio domínio e o `vercel.json`
reescreve para `https://toquedemulher-backend.vercel.app`. Nesse caminho a
requisição passa por duas bordas da Vercel: a do projeto do frontend e a do
backend. A documentação da Vercel informa que reescritas para origens externas
repassam o IP do visitante, mas também que a borda sobrescreve
`X-Forwarded-For` quando a requisição chega por outro proxy e só aceita um
`X-Forwarded-For` personalizado no plano Enterprise (Trusted Proxy). Por isso o
IP visto pelo backend nesse caminho precisa ser confirmado por teste.

**Resultado da verificação:** _pendente_ (ver abaixo).

### Como verificar sem registrar IPs

1. Faça deploy temporário (branch sem merge) de uma rota que devolva apenas
   resumos HMAC do `request.client.host` e dos cabeçalhos, nunca o IP.
2. Acesse a rota diretamente no domínio do backend e, da mesma rede, pelo
   domínio do frontend com o `vercel.json` apontando para esse preview.
3. Se os resumos de `request.client.host` forem iguais, o proxy preserva o IP do
   cliente. Se forem diferentes e o país não corresponder ao seu, o backend está
   vendo o IP de saída da Vercel e todos os clientes do site dividem o mesmo
   limite.
4. Apague as branches temporárias.

## Limite em memória ou Redis

O contador fica na memória de cada processo:

- no Docker, cada worker do Uvicorn (2 por padrão) tem o próprio contador;
- na Vercel, cada instância da função tem o próprio contador, que reinicia em
  cold starts; com várias instâncias, o limite efetivo é 30 × instâncias.

Isso é aceitável **temporariamente**, enquanto o tráfego é baixo: o limite segue
barrando repetição rápida da mesma origem, e o backend já trata `429` do Melhor
Envio sem inventar preço. Não é suficiente para produção com tráfego real ou sob
abuso, porque não é global nem determinístico. Opções, em ordem de preferência
para este projeto:

1. **Tabela no Postgres do Supabase** (sem nova infraestrutura): uma linha por
   chave/janela com `INSERT ... ON CONFLICT DO UPDATE`, limpeza periódica. Uma
   escrita a mais por requisição limitada.
2. **Regra de rate limit no firewall da Vercel**, aplicada na borda do projeto
   do frontend, que enxerga o IP real antes do proxy. Conferir disponibilidade
   no plano da equipe.
3. **Redis gerenciado** (por exemplo Upstash pelo Marketplace da Vercel): nova
   dependência e nova credencial.
