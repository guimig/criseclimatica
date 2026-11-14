# Roadmap consolidado — situação de referência em 14/11/2026

> **Leitura:** este arquivo conserva checklists e registros de fases anteriores; o status de CI/cron e integração declarado nessas fases não deve ser extrapolado para hoje. Critérios consultivos atuais: [v4](CLASSIFICACAO_CONSULTIVA.md). Operação: [manual](OPERACAO_E_MANUTENCAO.md).

## Situação reconciliada com o código de 14/11/2026

- [x] Classificador `araquari-risk-v4` e interpretação multifontes com previsão INMET/CPTEC, boletins elegíveis e referências instrumentais, preservando critérios, prazos e evidências.
- [x] Interface principal e detalhes, com atualização automática de publicações e rejeição de identidade inconsistente dos JSON.
- [x] Disparo externo cron-job.org a cada 30 min e backup GitHub em 7/37 com corte de idade de 25 min; o workflow de publicação segue em `pages.yml`.
- [x] Recuperação de históricos publicados com validação e repetição limitada de erros transitórios; falha de histórico obrigatório bloqueia a publicação para evitar perda silenciosa.
- [x] Conector Defesa Civil SC com extração de texto completo, distinção de monitoramento/alerta e validação limitada de janelas.
- [ ] **Recuperar a conectividade da Defesa Civil SC no runner de produção**: diagnóstico de 13/11 encontrou falha TCP/HTTP, embora o portal tenha respondido em ambiente de teste separado. Não registrar integração como operacional.
- [ ] Conferir periodicamente dados publicados e estado de cada fonte, não apenas sucesso do workflow. Um build verde não certifica a entrega de todos os provedores.
- [ ] Formalizar interpretação das ambiguidades entre PN 13 e PN 14 antes de traduzir regras acadêmicas em comportamento da aplicação.
- [ ] Implantar backup independente apenas após definir retenção, custo, controle de integridade e recuperação; Pages não é backup.
- [ ] Validar calibração, unidades, períodos e representatividade de estações antes de promover comparações exploratórias a indicadores científicos.

### Evidência de execução pontual, não garantia futura

Na consulta ao histórico de Actions em 14/11/2026, a execução [43597550787](https://github.com/guimig/criseclimatica/actions/runs/43597550787), iniciada em 13:00 UTC por `workflow_dispatch`, concluiu com sucesso às 13:04 UTC. O resultado confirma aquele workflow, **não** disponibilidade de cada fonte nem ausência de falhas em ciclos futuros.

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


## Estado atual verificado

- Cobertura configurada: vinte municípios de SC/PR, com Araquari como referência principal.
- Painel essencial, dados detalhados, comparação de modelos, seis referências normativas, temas e gráficos interativos em produção.
- Históricos compactos em Pages, sem banco ou armazenamento externo independente.
- Verificação agendada de idade e atualização automática no navegador implementadas; atrasos do Actions e fontes externas permanecem limitações explícitas.
- CI e navegação em desktop/celular confirmados para os pacotes anteriores. Esta revisão acrescenta regressões de troca de saída, contratos frontend, versões municipais e atualização da comparação.

As seções de integração abaixo registram a evolução de cada etapa; contagens e verificações ainda pendentes ali se referem àquela etapa. Consulte a [revisão geral](REVISAO_APLICACAO_2026_11_08.md) para as correções atuais.

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


## Síntese consultiva — Araquari como foco do IFC

- [x] Relógio injetável nos testes do coletor Cemaden, preservando expiração real em produção.
- [x] Intervalo da precipitação atual preservado e unidades horárias/diárias validadas.
- [x] Síntese principal fixa em Araquari; outros municípios em contexto complementar.
- [x] Antecedentes por estação, maiores janelas de chuva 3/6 h, máximos de vento/rajada e referências consecutivas de calor.
- [x] Avisos por IBGE, com coincidência temporal somente quando fuso e validade forem explícitos.
- [x] Sugestões rastreáveis e consultivas, retiradas após vencimento.
- [x] Contexto exploratório de temperatura por pares, sem estatística de erro de previsão.
- [x] Registro limitado da última previsão publicada e comparação das mesmas horas futuras.
- [x] Comparação diária CPTEC/Open-Meteo sem diferença numérica até conciliação de limites do dia.
- [ ] Validar institucionalmente ambiguidades do protocolo e critérios de calor, antes de classes automáticas.
- [ ] Avaliar desempenho de previsões somente com emissão, horizonte e observações correspondentes preservados.

Detalhamento: [síntese consultiva](SINTESE_CONSULTIVA_ARAQUARI.md).


## Painel objetivo — PN 13 e PN 14/2026

- [x] Substituir referência ativa ao protocolo local e preservar cópias das normas atuais.
- [x] Priorizar Epagri/Ciram no enquadramento qualitativo, sem converter cores INMET ou valores de modelo em nível institucional.
- [x] Página inicial compacta, clara e independente; área detalhada em `dados.html`.
- [x] Mediana de chuva com amostra mínima, extremos e horários rastreáveis.
- [x] Histórico observado por estação com sete dias de retenção e proteção de continuidade.
- [x] Gráficos interativos por variável, fonte/tipo e período, com suporte a teclado.
- [x] Previsão de até dez dias para contextualizar preparação de maior antecedência.
- [ ] Validar externamente impactos/decretos e decisões formais; não inferidos pelo aplicativo.
- [ ] Resolver institucionalmente a divergência sobre avaliações no laranja entre PN 13, art. 10, I, e PN 14, art. 8º, III.

[Metodologia atual](PAINEL_ARAQUARI_PN13_PN14.md).


## Evolução visual, apoio objetivo e retrospectiva

- [x] Cabeçalho com navegação por seções e tema escuro persistente.
- [x] Estados neutros que distinguem rotina, cobertura parcial e atenção.
- [x] Referências numéricas INMET auxiliares e cruzamento por variável/horário/proximidade.
- [x] Passado observado e previsão no gráfico inicial, com intervalos compatíveis.
- [x] Memória de episódios amostrados e janelas de validade dos avisos.
- [x] Proteção de continuidade e testes de idempotência dos históricos.

[Critérios e limitações](LEITURA_MULTIFONTES_E_MEMORIA.md).
