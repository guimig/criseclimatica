# Coleta e publicação a cada 30 minutos

## Configuração ativa

O usuário configurou o cron-job.org para chamar a API GitHub com `*/30 * * * *`, habilitado e sem expiração de agendamento: minutos **00 e 30**, todas as horas, todos os dias, incluindo noites e fins de semana. São 48 oportunidades diárias de coleta. A credencial foi inserida pelo usuário diretamente no serviço, fora do chat e do repositório.

O teste do serviço retornou **HTTP 204** e criou a execução `42638342239`, evento `workflow_dispatch`, em 09/11/2026 às 14h48 UTC (11h48 de Brasília). Isso comprova aceitação do disparo, não substitui conferir a coleta e o deploy. Confira a execução no Actions e `data/dashboard.json.generated_at` após o término.

Disparos `workflow_dispatch`, manuais e pushes sempre iniciam coleta, validação e publicação. O cron nativo GitHub usa `7,37 * * * *` como **reserva**. Apenas nesses eventos `schedule` há verificação de idade: publica se a última versão tiver pelo menos **25 minutos**, estiver vencida, inválida ou não puder ser verificada. Quando o serviço externo publica normalmente, a reserva encontra dados recentes e não repete as chamadas às fontes. Não há filtro de 35 minutos sobre o disparo primário.

A página verifica versões novas a cada minuto com a aba visível. Não precisa ficar aberta para a coleta. Cron é horário programado de início: aparecer na página depende de concluir a coleta e o deploy. O disparo externo reduz a dependência do agendamento GitHub, mas o pipeline continua dependendo de runners, provedores e Pages. Dados ausentes não viram zero; prazos científicos e regras de classificação não foram estendidos.

## Configuração e manutenção da requisição externa

A API e o utilitário abaixo permitem reconstruir a configuração quando necessário. Não crie outro job incondicional sem desativar o anterior, para evitar duplicação.

Em um serviço com requisições HTTP programadas, use:

- Método: `POST`.
- URL: `https://api.github.com/repos/guimig/criseclimatica/actions/workflows/pages.yml/dispatches`.
- Corpo JSON: `{"ref":"main"}`.
- Cabeçalhos: `Accept: application/vnd.github+json`, `Content-Type: application/json`, `X-GitHub-Api-Version: 2022-11-28` e `Authorization: Bearer TOKEN_PRIVADO`.
- Frequência: cada 30 minutos, todos os dias e horários. O serviço deve manter retries de falhas HTTP/rede com limite e registrar falhas.
- Credencial: token granular restrito ao repositório `guimig/criseclimatica`, com permissão **Actions: write**, armazenado exclusivamente no campo privado de credenciais/cabeçalhos do serviço. Não coloque token em URL, navegador, commits ou arquivos públicos. Defina vencimento e um responsável pela renovação.
- Resposta esperada: HTTP 204 significa disparo aceito; confirme depois build/deploy e `data/dashboard.json.generated_at` mais recente. Aceitação não comprova publicação concluída.

Em um host externo com Python 3.11+, o mesmo acionamento pode ser feito por:

```sh
python scripts/dispatch_update.py
```

Nesse host, configure previamente `GITHUB_UPDATE_TOKEN` no mecanismo privado de variáveis do serviço. O utilitário chama apenas o workflow e branch especificados, não segue redirecionamentos e não registra o token ou o corpo de erros.

## Validação e continuidade

1. Confira job habilitado, expressão `*/30 * * * *` e ausência de restrição de dia/horário.
2. Faça teste e confirme HTTP 204. Não abra nem exporte o cabeçalho de autorização em registros públicos.
3. Confira workflow `workflow_dispatch`, build/deploy concluídos e publicação mais recente no site.
4. Observe os ciclos automáticos seguintes antes de declarar estabilidade contínua. O primeiro teste é manual, não comprova meses de disponibilidade.
5. Mantenha apenas um job primário e o cron GitHub como reserva por idade. Falhas de consulta ou validade sempre solicitam recuperação.
6. Renove o token privado antes do vencimento definido no GitHub. Não se publica a credencial nem seu valor em arquivos ou logs.

O GitHub continua executando o pipeline mesmo com disparo externo. Esse mecanismo reduz a dependência do evento `schedule`, mas não elimina indisponibilidade de runners, provedores ou Pages. Referência: [API oficial de workflows](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
