# Avisos INMET de perigo em municípios limítrofes

A interface de Araquari destaca **somente Perigo e Grande Perigo** (faixa de Alerta ou superior, como referência de prioridade) em municípios limítrofes, logo abaixo do nível de risco local. **Perigo Potencial, Atenção e severidades inferiores não acionam esse destaque**; quando disponíveis, os avisos menos graves permanecem no bloco recolhível **Avisos · INMET**.

## Abrangência e coleta

A relação de municípios limítrofes é mantida em \`config/araquari_limitrofes.json\`, com nomes e códigos IBGE de sete dígitos. Essa é uma relação **territorial**, não uma distância radial entre pontos amostrais. A seleção usa correspondência exata do código IBGE retornado pelo INMET. O conjunto inclui municípios já presentes na previsão regional e outros não incluídos nas rotinas meteorológicas gerais, sem gerar consultas extras de previsão.

A mesma resposta da API INMET para \`hoje\`/\`futuro\` é reutilizada na leitura adicional; em cada publicação, \`alerts.json\` mantém as localidades de previsão no campo original \`locations\` e adiciona \`bordering_locations\`. Em falha de consulta, avisos previamente obtidos são mantidos em \`retained_bordering_locations\` até o término oficial, sob indicação de falta de reconfirmação. Nenhum desses campos altera a lista de localidades, o cálculo de chuva/vento ou a classificação de Araquari.

O \`dashboard.json\` publica \`bordering_notice_context\`: identificador único do aviso, severidade exata, início/fim UTC, municípios abrangidos, situação de reconfirmação e link do INMET. Avisos sem janela temporal válida não são destacados como vigentes. Avisos cuja abrangência também inclua Araquari são tratados no circuito de avisos municipais, não duplicados como perigos exclusivamente vizinhos. A mera ausência do aviso da consulta atual não comprova cancelamento; cancelamentos expressos removem a evidência recuperada.

## Regras de apresentação e classificação

- **Grande Perigo**: destaque reforçado, identificado com o grau oficial INMET.
- **Perigo**: destaque de perigo no entorno imediato.
- **Perigo Potencial e níveis de Atenção ou inferiores**: sem destaque especial e sem notificação regional automática, mantidos apenas no bloco recolhível INMET quando houver aviso válido.
- **Sem duplicação**: o mesmo identificador INMET destacado é omitido do bloco recolhível. Avisos menos graves de municípios limítrofes (mesmo fora do raio de 40 km) podem permanecer nesse bloco.
- **Evento programado**: visível como programado, jamais apresentado como já em curso.
- **Evento encerrado**: removido ao atingir o fim oficial.
- **Fonte desatualizada**: aviso previamente coletado permanece até o fim oficial, com aviso de que revisão/cancelamento não foram reconfirmados.

O painel sempre explicita que **Araquari não consta da abrangência confirmada dessa seção** e que o destaque não altera automaticamente o nível consultivo de risco. O alerta vizinho não substitui medições do campus nem avisos da Defesa Civil.

## Integração Telegram (repositório separado)

A integração do bot lê \`dashboard.bordering_notice_context\` **somente quando a publicação estiver consistente**. Não recalcula nível local. Envia uma mensagem **distinta das transições consultivas** para aviso INMET de \`Perigo\` ou \`Grande Perigo\`, apenas quando já vigente, com município, período oficial, situação local e link único para o painel.

Uma assinatura estável por **dia e fenômeno** evita repetição entre IDs e municípios diferentes relacionados ao mesmo evento. Elevação de \`Perigo\` para \`Grande Perigo\` pode provocar nova comunicação. \`Perigo Potencial\` não gera envio automático. Primeira execução com dados válidos apenas inicializa uma linha de base silenciosa, sem comunicar retrospectivamente avisos que já estavam em vigor. Anúncios confirmados são persistidos na branch \`bot-state\` do repositório Telegram.

**Ordem de implantação:** publicar e validar primeiro a alteração do observatório. Depois mesclar o PR do bot, executar \`dry_run\` e conferir os logs do cursor inicial. Na primeira rodada válida não haverá notificação de avisos anteriormente existentes. Notificações novas seguirão o fluxo do cron-job.org e do backup do GitHub, sem novo segredo.

## Testes e reversão

O teste sintético cobre abrangência exata, aviso local simultâneo, municípios não limítrofes, cada severidade, duplicidade, expiração, cancelamento e falha do provedor. O teste JavaScript cobre visibilidade com e sem risco local, janela vencida e links oficiais. O bot valida migração silenciosa, novo aviso, upgrade, falha no envio e repetição.

Para reverter a interface, reverter o merge do PR do observatório. Para cessar notificações regionais, reverter o PR do bot (sem zerar o estado durável). A persistência atual de outras notificações permanece intacta.


## Leitura humana e endereços INMET

O link do destaque do entorno abre **https://avisos.inmet.gov.br/**, portal oficial legível. O código numérico do registro proveniente da API não é transformado em URL — o endereço antigo `alertas2.inmet.gov.br/{id}` não é uma página confiável. Os riscos potenciais e as instruções coletados do INMET podem ser lidos diretamente no aviso do painel. Quando necessário, o feed [RSS/XML](https://apiprevmet3.inmet.gov.br/avisos/rss) é oferecido somente como recurso técnico em Dados e fontes. Os avisos regionais continuam separados dos emitidos para Araquari.


## Destaque recolhível e cores por gravidade

A página inicial apresenta avisos graves do entorno em um bloco nativo `<details>`, inicialmente fechado. Mesmo recolhido, o cabeçalho permanece visível com a indicação **INMET · contexto regional**, o maior grau oficial entre os avisos, a quantidade de avisos vigentes/programados e os municípios (até três nomes, com contagem dos adicionais). Ao expandir, são exibidos os períodos, os riscos/instruções disponíveis, o link ao portal oficial e a ressalva de que Araquari não está na abrangência municipal confirmada.

- **Perigo**: cabeçalho, borda e marcador em laranja.
- **Grande Perigo**: cabeçalho, borda e marcador em vermelho (prevalece quando há diferentes graus no mesmo bloco); cada aviso dentro do conteúdo conserva sua própria gravidade.
- **Perigo Potencial**: não aciona o bloco; continua nos avisos normais recolhíveis do INMET.

A interação usa `summary`, sem JavaScript adicional para alternar o recolhimento: funciona por teclado e leitor de tela. O estado aberto é preservado durante re-renderizações de dados na página, mas é reinicializado quando não houver mais avisos elegíveis ou após recarregamento completo. A classificação de risco de Araquari e as notificações do Telegram não são afetadas.
