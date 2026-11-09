# Recuperação do carregamento — 09/11/2026

## Evidências

A captura das 19h05 mostrava “Atualização indisponível”, cartões vazios e uma mensagem de última leitura preservada/validade perdida. As execuções externas das 17h00, 17h30, 18h00, 18h30 e 19h00 concluíram com sucesso; a publicação das 19h00 terminou às 19h04. Os arquivos `latest.json`, `dashboard.json` e `observation_history.json` recuperados tinham `generated_at` e `publication_at` iguais a `2026-11-09T22:04:03Z`. A home abriu depois no navegador com os quatro indicadores preenchidos.

Não há log do navegador do celular no instante da falha. Portanto, não é possível distinguir definitivamente rede/timeout de uma divergência transitória do CDN. A captura demonstra ausência de publicação carregada naquela aba; não demonstra atraso do agendador nem vencimento dos dados publicados.

## Defeitos reproduzidos e correção

- Uma divergência de `publication_at` lançava exceção para fora do laço antes de chegar à segunda tentativa. Rede, HTTP e JSON também interrompiam a primeira leitura. A home passa a repetir uma vez o conjunto completo com uma chave de cache nova. Os contratos e a recusa de fixtures, dados futuros e regressão de versão permanecem.
- O polling chamava `onSuccess` ao ler o manifesto, antes de carregar a publicação. A home também não marcava falha de carga como motivo para tentar novamente a mesma versão. O sucesso agora depende do carregamento; falhas persistem até a recuperação e continuam sujeitas ao limite de frequência.
- `riskPresentation(null)` tratava ausência de carga como expiração, e o aviso afirmava preservar dados inexistentes. A primeira carga malsucedida passa a mostrar “Dados indisponíveis”, sem alegar validade perdida ou cópia anterior.
- O rodapé ainda dizia 40 minutos. Foi alinhado à coleta de 30 minutos. Os URLs dos scripts alterados recebem nova versão para atualização do cache do navegador.

## Validação

323 testes Python aprovados; cinco suítes JavaScript, sintaxe, build e validação offline aprovados. A reprodução isolada com o código anterior termina sem dados e com `fetchError=true`; com a correção, o mesmo cenário termina com dados e `fetchError=false`.

`tests/dashboard_loading.cjs` cobre carga normal, primeira resposta divergente, rede, HTTP/JSON, falha persistente, mensagens, recuperação da mesma versão pelo polling, preservação da leitura, histórico ausente, fixture e regressão de versão. O teste é obrigatório no CI e antes das coletas. `tests/ui_publication_refresh.py` acrescenta os cenários de primeiro acesso no Chromium do CI. O resultado do navegador no CI deve ser conferido no PR.

A correção aumenta a tolerância a falhas transitórias; não garante disponibilidade de rede ou propagação instantânea do Pages. Não altera critérios meteorológicos, prazos de validade, estações ou agenda de coleta. Para reverter, reverter o commit correspondente.
