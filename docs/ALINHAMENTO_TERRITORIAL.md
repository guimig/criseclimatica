# Áreas comuns entre Open-Meteo, Cemaden e METAR

## Escopo e núcleos operacionais

Os dez municípios anteriores permanecem. A expansão tem a finalidade de amostrar áreas próximas das estações das três fontes, sem equiparar suas naturezas: Open-Meteo é estimativa/previsão de modelo; Cemaden e METAR são observações instrumentais pontuais.

| Núcleo | Municípios | Referências METAR na região |
|---|---|---|
| Norte de SC | Araquari, Joinville, São Francisco do Sul, Itapoá, Garuva, Balneário Barra do Sul, Barra Velha, Jaraguá do Sul, Guaramirim | SBJV; outros somente conforme distância real |
| Vale e foz do Itajaí | Blumenau, Itajaí, Navegantes, Penha, Balneário Piçarras, Gaspar, Pomerode | SBNF, SSBL quando houver boletim |
| Grande Florianópolis | Florianópolis, São José/SC | SBFL |
| Curitiba e planalto próximo | Curitiba, São José dos Pinhais | SBBI, SBCT |

Os agrupamentos são operacionais. Não são regiões oficiais do IBGE nem uma classificação de homogeneidade climática. O planalto não deve ser tratado como equivalente ao litoral por estar relativamente perto. Os pontos em `config/locations.json` são aproximações curadas para amostragem, não centroides oficiais ou limites municipais. Códigos municipais foram conferidos nas fontes IBGE; as coordenadas devem ser refinadas quando houver uma referência instrumental específica para comparação.

## O que passa a ser comum

Todos os coletores usam a mesma lista de vinte municípios e pontos de referência. Open-Meteo consulta as coordenadas; Cemaden consulta os vinte códigos IBGE para acumulados e duas UFs (SC/PR) para sensores; METAR associa os seis aeródromos consultados aos mesmos pontos. As demais fontes georreferenciadas também recebem a lista, mas uma fonte estadual ou sem cobertura não se torna automaticamente uma medição de todos os municípios.

As consultas de sensores por UF compartilham autenticação e limitador PED. Há no máximo 30 mil registros por UF, 60 mil no conjunto, com resposta HTTP de tamanho limitado. Uma UF indisponível não apaga dados válidos da outra e a cobertura parcial fica explícita. O acréscimo de municípios aumenta as consultas IBGE: o agendamento permanece de três horas e o job tem limite de quinze minutos; não há aumento da taxa de requisições permitida.

## Levantamento territorial

O arquivo `territorial_alignment.json` e o painel de áreas comuns não calculam desempenho. São um inventário de candidatos:

1. Localizar estações com leitura válida até 25 km do ponto municipal.
2. Verificar também que Cemaden e METAR estejam separados por até 25 km; estarem individualmente perto do ponto não basta.
3. Registrar a distância à referência de grade retornada pelo Open-Meteo. Não substituir silenciosamente a posição da grade pela posição solicitada. Sem grade conhecida, o candidato permanece não verificado.
4. Sinalizar prioridade geométrica até 10 km; conservar distância, núcleo e horário de cada fonte.
5. Informar o maior intervalo entre referências e se ele cabe na janela exploratória de sessenta minutos.
6. Identificar variável potencialmente comum nas três fontes apenas quando os campos e unidades estejam confirmados. Temperatura pode ser candidata quando existe sensor Cemaden 60 em °C; isso não comprova equivalência de exposição ou calibração.

Esses limites são parâmetros exploratórios do projeto, não normas científicas de equivalência. Uma diferença de sessenta minutos pode ser relevante; relevo, exposição, altitude e dinâmica local podem inviabilizar até pares separados por poucos quilômetros. `comparison_ready` permanece falso. Contagens de candidatos não são índices de qualidade.

O inventário privilegia até seis estações Cemaden próximas, incluindo sensores de temperatura quando presentes, e até seis aeródromos; publica até seis conjuntos por município. A seleção dos painéis gerais (24 estações em 130 km e METAR até 180 km) permanece independente. O conjunto de estudo é propositalmente mais próximo que o contexto regional geral.

## Altitude, chuva e horizonte da previsão

A altitude devolvida pelo Open-Meteo é registrada quando disponível; ela é uma referência do processamento do provedor, não altitude medida em estação. Altitudes das estações permanecem desconhecidas até confirmação cadastral, sem inferência a partir da cidade. Não se considera a altitude conciliada.

A consulta de acumulados Cemaden por IBGE não traz, por si só, coordenadas verificadas de todos os pluviômetros. Esses acumulados aparecem como cobertura municipal de consulta e não como pares espaciais comprovados. METAR não fornece acumulado pluviométrico em mm, portanto não integra uma comparação tripla de chuva.

Uma previsão de chuva futura não pode ser comparada diretamente à chuva observada nas últimas 24h. Também não se mede acurácia de previsão usando apenas a estimativa corrente do modelo. Antes de qualquer validação, será preciso preservar emissão e horizonte, ajustar intervalos de acumulação/vento e alinhar as observações no mesmo período. Não há novo arquivo histórico externo nesta etapa.

## Evidência e operação

Os testes cobrem candidatos próximos, estações em lados opostos, grade distante, unidades divergentes, fonte ausente, referências vencidas, defasagem temporal, consultas SC/PR com falha parcial e repetição idempotente. O histórico compacto aceita 20 × 366 registros, com teste de tamanho abaixo do limite atual de recuperação. O validador recusa alegações de prontidão científica. O teste JavaScript verifica as mensagens e a expiração do levantamento.

Após publicação, conferir quantos municípios têm sobreposição real e quantos possuem alguma variável comum confirmada. Três redes próximas podem ter zero variáveis comuns; o sistema deve mostrar essa lacuna, não inventar medições. A inspeção visual em navegador continua necessária.

Fontes: [IBGE — códigos municipais](https://www.ibge.gov.br/explica/codigos-dos-municipios.php), [Open-Meteo — API](https://open-meteo.com/en/docs), [PED — parâmetros de consulta](https://sws.cemaden.gov.br/PED/api/ui/swagger.json), [NOAA/AWC](https://aviationweather.gov/data/api/).

Reversão: revert do PR e nova publicação pelo workflow existente, preservando históricos. O armazenamento, os segredos e os limites de autenticação anteriores permanecem.
