# Roadmap consolidado — 06/11/2026

## Direção vigente

Python + GitHub Actions + GitHub Pages. Prioridade: Araquari e região; Brasil agregado em etapa posterior. Sem banco pago, Sheets, Drive ou histórico externo independente nesta fase. Preservar as fontes que funcionam e completar sua validação antes de ampliar armazenamento.

## Base integrada na main: PRs 1–11

- [x] Portal responsivo; previsão Open-Meteo; dez municípios.
- [x] Catálogos INMET automático e convencional; proximidade não significa representatividade municipal.
- [x] Avisos INMET por IBGE, METAR e históricos compactos de publicações/avisos.
- [x] Adaptador INMET recente implementado, ainda condicionado a credencial e validação real.
- [x] Arquivo anual INMET e seleção de estação com cobertura pluviométrica válida.
- [x] NASA POWER, CPTEC, Epagri GIS, avisos e previsão editorial.
- [x] Cemaden SGAA, acumulados e sensores recentes com limite compartilhado.
- [x] Coletor experimental Defesa Civil SC com falhas explícitas.

Evidência de operação: [execução 42255045977](https://github.com/guimig/criseclimatica/actions/runs/42255045977), commit `3b8c177`, em 06/11/2026. O log real registra Open-Meteo 10/10, avisos INMET, METAR, NASA, Cemaden acumulados/sensores, CPTEC, INMET anual e os três produtos Epagri disponíveis. INMET recente não configurado e Defesa Civil SC indisponível. Disponibilidade global não comprova todas as variáveis em todos os municípios nem operação contínua.

## Pacote de confiabilidade implementado nesta alteração

- [x] Total previsto de 24h condicionado a janela completa, horários únicos e valores válidos; cobertura e parcial separados.
- [x] Estado e diagnóstico Cemaden por município.
- [x] Ocultação de leituras vencidas e reavaliação de idade no navegador.
- [x] Resumo de cobertura por fonte/localidade, variáveis, estações e referências.
- [x] Publicação parcial com Open-Meteo fora do ar e outras fontes operacionais; falha total preserva publicação anterior.
- [x] Proteção contra desaparecimento do histórico diário previamente marcado como publicado.
- [x] Testes de regressão Python, cenários JavaScript sem rede e validação dos artefatos.
- [ ] Confirmar CI remoto e primeira publicação real deste pacote após integração.
- [ ] Inspeção visual em celular e desktop, incluindo município sem dados e atualização parcial.

## Próxima etapa — comprovar cobertura e continuidade

1. Auditar vários ciclos, incluindo agendados: sucesso, tempo de execução, falhas e atraso por fonte.
2. Conferir estações, horários, variáveis e unidades Cemaden realmente retornadas para cada município; não presumir temperatura ou vazão onde só existe pluviometria.
3. Definir unidades dos sensores ainda desconhecidos somente com documentação oficial e exemplares reais.
4. Ampliar o quadro de cobertura para INMET recente e demais produtos conforme suas medições forem confirmadas.
5. Avaliar frequência maior somente depois de medir estabilidade, quotas e duração.

## Completar integrações prioritárias

- [ ] Telemetria Epagri/Ciram por modalidade autorizada; o GIS atual é apenas cadastro.
- [ ] Acesso legítimo e teste real do INMET recente.
- [ ] Canal automatizado acessível da Defesa Civil SC e, quando disponível, Araquari; notícias não são alertas vigentes verificados.
- [ ] Confirmar unidades, intervalos diários e representatividade antes de ampliar comparações.

## Evolução posterior

1. Mapa de estações, origem, distância, idade e cobertura.
2. Hidrologia Cemaden/ANA: selecionar estações por bacia e posição no rio, não só proximidade.
3. Marés, ondas, radar e satélite após verificar autorização, estabilidade e área coberta.
4. Comparação modelo/observação com intervalos e horizontes compatíveis.
5. Séries observadas, normais, anomalias e tendências com cobertura mínima definida; snapshots publicados de modelo não servem como série climatológica.
6. Retenção seletiva e recuperação de históricos somente após decisão de avançar essa etapa. Manter consolidações dos dias normais e detalhes de eventos selecionados, sem crescimento contínuo do Git.
7. Visão Brasil por agregados.

Documentos anteriores em `docs/` registram o desenvolvimento e as limitações de cada etapa. Este arquivo e o README consolidam as prioridades vigentes.

## Ampliação das estações Cemaden e METAR

- [x] Cemaden: seleção de até 24 estações em 130 km por município (antes seis em 85 km); mesma consulta regional SC e limitador PED preservados.
- [x] Acumulados municipais: todas as estações válidas ficam acessíveis na interface; detalhes recolhidos após seis cartões.
- [x] METAR: consulta única de seis aeródromos SC/PR e referências por município até 180 km, com contexto regional explicitado acima de 100 km.
- [x] Mantida a observação principal METAR dentro de 100 km, com formatos legados preservados.
- [x] Logs públicos de contagem de estações, testes de raio, completude da seleção e boletins ausentes.
- [ ] Confirmar contagens reais no runner após integração; código consultado não significa boletim disponível.

Ver [Ampliação das estações](AMPLIACAO_ESTACOES.md).

## Alinhamento territorial das três fontes

- [x] Cadastro compartilhado ampliado para vinte municípios SC/PR em quatro núcleos operacionais, preservando os dez anteriores.
- [x] Open-Meteo e consultas municipais Cemaden usam os mesmos pontos/códigos; sensores Cemaden consultam SC e PR, com falha por UF explícita.
- [x] METAR mantém os seis aeródromos e associações por distância aos vinte pontos. Município não implica estação disponível.
- [x] Inventário de proximidade até 25 km, distância entre estações, janela temporal de 60 min e referência de grade do modelo.
- [x] Variável potencial comum somente quando unidade/campo confirmados; sem chuva METAR inventada e sem métrica de precisão.
- [x] Histórico de modelo continua limitado a 366 dias, com limite de registros compatível com vinte pontos e proteção contra perda.
- [ ] Conferir cobertura real, candidatos por núcleo e unidades após a primeira publicação.
- [ ] Obter coordenadas/altitudes verificadas de todos os pluviômetros e metadados dos sensores antes de comparação científica.
- [ ] Planejar previsões com emissão/horizonte preservados e observações com mesma janela antes de validar desempenho.

Os núcleos não certificam semelhança climática. Ver [Alinhamento territorial](ALINHAMENTO_TERRITORIAL.md).
