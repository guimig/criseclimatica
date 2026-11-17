# Avisos INMET de perigo em municípios limítrofes

A interface de Araquari exibe **Perigo** e **Grande Perigo** no entorno imediato em um painel exclusivo, logo abaixo do nível de risco local. **Perigo Potencial** aparece como informação regional secundária, sem a mesma ênfase.

## Abrangência e coleta

A relação de municípios limítrofes é mantida em \`config/araquari_limitrofes.json\`, com nomes e códigos IBGE de sete dígitos. Essa é uma relação **territorial**, não uma distância radial entre pontos amostrais. A seleção usa correspondência exata do código IBGE retornado pelo INMET. O conjunto inclui municípios já presentes na previsão regional e outros não incluídos nas rotinas meteorológicas gerais, sem gerar consultas extras de previsão.

A mesma resposta da API INMET para \`hoje\`/\`futuro\` é reutilizada na leitura adicional; em cada publicação, \`alerts.json\` mantém as localidades de previsão no campo original \`locations\` e adiciona \`bordering_locations\`. Em falha de consulta, avisos previamente obtidos são mantidos em \`retained_bordering_locations\` até o término oficial, sob indicação de falta de reconfirmação. Nenhum desses campos altera a lista de localidades, o cálculo de chuva/vento ou a classificação de Araquari.

O \`dashboard.json\` publica \`bordering_notice_context\`: identificador único do aviso, severidade exata, início/fim UTC, municípios abrangidos, situação de reconfirmação e link do INMET. Avisos sem janela temporal válida não são destacados como vigentes. Avisos cuja abrangência também inclua Araquari são tratados no circuito de avisos municipais, não duplicados como perigos exclusivamente vizinhos. A mera ausência do aviso da consulta atual não comprova cancelamento; cancelamentos expressos removem a evidência recuperada.

## Regras de apresentação e classificação

- **Grande Perigo**: destaque reforçado, identificado com o grau oficial INMET.
- **Perigo**: destaque de perigo no entorno imediato.
- **Perigo Potencial**: referência secundária, sem equipará-lo às duas classes mais graves.
- **Evento programado**: visível como programado, jamais apresentado como já em curso.
- **Evento encerrado**: removido ao atingir o fim oficial.
- **Fonte desatualizada**: aviso previamente coletado permanece até o fim oficial, com aviso de que revisão/cancelamento não foram reconfirmados.

O painel sempre explicita que **Araquari não consta da abrangência confirmada dessa seção** e que o destaque não altera automaticamente o nível consultivo de risco. O alerta vizinho não substitui medições do campus nem avisos da Defesa Civil.

## Integração Telegram (repositório separado)

A integração do bot lê \`dashboard.bordering_notice_context\` **somente quando a publicação estiver consistente**. Não recalcula nível local. Envia uma mensagem **distinta das transições consultivas** para aviso INMET de \`Perigo\` ou \`Grande Perigo\`, apenas quando já vigente, com município, período oficial, situação local e link único para o painel.

Um identificador derivado do ID oficial e do dia de início evita repetição. Elevação de \`Perigo\` para \`Grande Perigo\` pode provocar nova comunicação. \`Perigo Potencial\` não gera envio automático. Primeira execução com dados válidos apenas inicializa uma linha de base silenciosa, sem comunicar retrospectivamente avisos que já estavam em vigor. Anúncios confirmados são persistidos na branch \`bot-state\` do repositório Telegram.

**Ordem de implantação:** publicar e validar primeiro a alteração do observatório. Depois mesclar o PR do bot, executar \`dry_run\` e conferir os logs do cursor inicial. Na primeira rodada válida não haverá notificação de avisos anteriormente existentes. Notificações novas seguirão o fluxo do cron-job.org e do backup do GitHub, sem novo segredo.

## Testes e reversão

O teste sintético cobre abrangência exata, aviso local simultâneo, municípios não limítrofes, cada severidade, duplicidade, expiração, cancelamento e falha do provedor. O teste JavaScript cobre visibilidade com e sem risco local, janela vencida e links oficiais. O bot valida migração silenciosa, novo aviso, upgrade, falha no envio e repetição.

Para reverter a interface, reverter o merge do PR do observatório. Para cessar notificações regionais, reverter o PR do bot (sem zerar o estado durável). A persistência atual de outras notificações permanece intacta.
