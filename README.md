# toquedemulher-backend

## Configuracao de ambiente

1. Crie o arquivo `.env` a partir de `.env.example`.
2. Preencha as variaveis sensiveis:
   - `DATABASE_URL`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
3. Ajuste `CORS_ORIGINS` se seu frontend usar outra URL.

## Seguranca de configuracao

- O arquivo `.env` e variantes locais continuam ignorados via `.gitignore`.
- O arquivo `.env.example` documenta apenas placeholders seguros para versionamento.
