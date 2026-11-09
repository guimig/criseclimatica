# Coleta e publicação a cada 30 minutos

## Configuração ativa no repositório

O workflow `.github/workflows/pages.yml` usa `7,37 * * * *`: duas execuções por hora, 24 horas por dia, sete dias por semana, sem restrição de dia útil. São 48 oportunidades diárias de coleta. No horário de Brasília, por ter deslocamento inteiro de horas em relação ao UTC, os minutos continuam 07 e 37: 00h07, 00h37, …, 23h07 e 23h37. Os minutos fora da virada da hora evitam a concentração dos agendamentos no minuto zero.

Cada evento entregue inicia coleta, validação e publicação (`--force true`). A regra anterior que dispensava coleta antes de 35 minutos não é aplicada pelo workflow. O botão do site continua relendo os arquivos públicos, e a aba visível verifica versões novas a cada minuto. Não é necessário deixar a página aberta para a coleta server-side.

O instante da publicação depende de concluir a coleta e o deploy: o cron é horário programado de início, não promessa de aparecer na tela naquele segundo. Falhas de fontes, validações e omissões do agendador podem interromper o ciclo; dados ausentes não são substituídos por zero e prazos científicos não são artificialmente renovados.

## Disparo externo independente — preparado, ainda não ativado

O cron do GitHub já apresentou hiatos. Para reduzir essa dependência, configure um serviço externo para chamar `workflow_dispatch` da API GitHub, ou para executar `scripts/dispatch_update.py`, também com cadência de 30 minutos durante todo o dia. O serviço precisa de uma conta/host disponível e uma credencial própria. Nenhum agendador externo foi criado nem recebeu credenciais nesta alteração.

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

Para configurar a redundância sem duas coletas sistemáticas por ciclo, escolha um mecanismo primário: após confirmar o disparo externo funcionando, remova o `schedule` do GitHub e preserve `workflow_dispatch`/`push`, ou faça o serviço externo disparar apenas quando o `generated_at` estiver atrasado. A segunda opção é supervisão de atraso, não garantia de intervalo exato. Não deixe dois disparos incondicionais por meia hora sem avaliar a carga sobre as fontes.

## Ativação e validação

1. Mantenha o agendamento GitHub enquanto o externo não estiver ativo.
2. Configure o serviço externo e a credencial privada; rode um disparo de teste.
3. Confira um novo workflow `workflow_dispatch`, deploy concluído e horários efetivamente atualizados no site.
4. Confirme dois ciclos consecutivos sem intervenção e durante o período noturno antes de declarar estabilidade da cadência.
5. Só então retire o cron redundante ou mantenha supervisão por idade, conforme a opção escolhida.

O GitHub continua executando o pipeline mesmo com disparo externo. Esse mecanismo reduz a dependência do evento `schedule`, mas não elimina indisponibilidade de runners, provedores ou Pages. Referência: [API oficial de workflows](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event).
