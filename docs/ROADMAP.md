# Roadmap de desenvolvimento

## Fase 0 - Publicada no GitHub Pages

- Estrutura modular Python e contratos de resposta normalizados.
- Open-Meteo para sete pontos aproximados de SC.
- Interface responsiva com graficos e comparacao regional.
- Arquivos JSON para publicacao via Pages sem commits frequentes.
- Gatilho a cada tres horas, execucao manual e workflow de testes.
- Rotinas portaveis JSONL.GZ com teste de ida e volta.

O usuario confirmou a publicacao e o funcionamento do site. A comprovacao de ciclos regulares da coleta real em GitHub Actions continua relevante.

## Fase 1 - Observacoes instrumentais e confiabilidade

1. **Implementado em PR:** catalogo publico de estacoes INMET (metadados e proximidade; nao medidas).
2. **Implementado:** avisos do INMET associados por código municipal IBGE, com estado de indisponibilidade e sem inferência de fuso.
3. **Implementado:** boletins METAR dos aeroportos SBJV/SBNF, com identificação da estação e conversão de unidades.
4. **Parcial:** adaptador opcional de precipitação horária INMET desenvolvido; exige token e validação real. Integrações Cemaden/Epagri seguem pendentes.
5. **Implementado:** falhas de avisos, METAR e do adaptador INMET não paralisam a previsão e são identificadas na interface.
6. Revisao de coordenadas e representatividade territorial.

## Fase 2 - Historicos e armazenamento sem banco pago

1. Testar armazenamento autenticado no Google Drive com segredo GitHub.
2. **Parcial:** historico compacto de uma estimativa de modelo publicada por dia no Pages (366 dias), sem confundir com medidas; JSONL.GZ externo ainda pendente.
3. Criterios de retencao por fonte, escala temporal e uso efetivo.
4. Registrar metadados, latencia, cobertura e indicadores de qualidade.
5. **Parcial:** arquivo progressivo de avisos oficiais, que não deve ser interpretado como catálogo de desastres confirmados; séries detalhadas de episódios medidos ainda pendentes.
6. Benchmarks de leitura, escrita, recuperacao e uso de armazenamento.

## Fase 3 - Hidrologia, litoral e analise

1. Cemaden e ANA, sujeito a cadastro e credenciais.
2. Epagri/Ciram por modalidade de integracao autorizada.
3. Informacoes de mares, ondas, radar e cobertura de satelite.
4. Comparacao modelo versus estacoes, sem equiparar estimativa a medicao.
5. Catalogo de eventos meteorologicos e anomalias com verificacao.
6. Visao Brasil agregada e consultas sob demanda.

Ver [Histórico e estações](HISTORICO_E_ESTACOES.md) para a distinção entre catálogo INMET, observações e estimativas de modelo.

Para esta fase, consultar [Avisos INMET e METAR](AVISOS_E_METAR.md).

Ver também [Chuva observada e histórico de avisos](CHUVA_E_HISTORICO_AVISOS.md).

## Prioridade vigente — amadurecer integrações antes de ampliar armazenamento

Por decisão do mantenedor, o avanço para backup histórico independente e
novos bancos/arquivos externos foi **postergado**. Nesta etapa foram preparados:

- [x] Diagnóstico acionável da pluviometria INMET (credencial, bloqueio,
  ausência de leitura, falta de cobertura e erros) sem inventar valores.
- [x] Conector Cemaden PED baseado no contrato oficial de acumulados recentes,
  sujeito a token JWT autorizado e teste em ambiente real.
- [x] Integração NASA POWER de estimativas diárias em grade, com coleta
  moderada, transparência da fonte e identificação dos dias UTC.
- [x] Painel público de estado de cada fonte, com falhas independentes.
- [ ] Validar o novo serviço NASA na primeira execução real do workflow.
- [ ] Validar INMET/Cemaden com credenciais legítimas, quando disponíveis,
  sem contornar proteções de acesso.
- [ ] Obter canal oficial de acesso automático de Epagri/Ciram e ANA.
- [ ] Ampliar variáveis observadas, cobertura de estações e representatividade
  somente após confirmação das integrações.

Ver [Integrações e chuva observada](INTEGRACOES_FASE_ATUAL.md).

### Ampliação regional — CPTEC, redes INMET e Defesa Civil SC

- [x] Catálogo automático INMET; nova consulta ao catálogo **convencional**, separados por tipo e localização.
- [x] Links oficiais para BDMEP, tabelas INMET, Defesa Civil SC, Defesa Civil Araquari e Epagri/Ciram.
- [x] Adaptador CPTEC/INPE XML para comparação de previsão diária, com indisponibilidade explícita.
- [x] Coletor experimental de publicações da Defesa Civil SC via WP/RSS, sem alegar vigência de alertas.
- [ ] Validar no runner GitHub as consultas reais de CPTEC e SC; estas interfaces não oferecem SLA/contrato estável para o projeto.
- [ ] Solicitar interface machine-readable autorizada à Defesa Civil de Araquari e SC para alertas com vigência/área.
- [ ] Integrar dados instrumentais de chuva de redes com API autorizada e horários verificáveis.
- [ ] Validar dados públicos estruturados de estações Epagri/Ciram na região.

**Decisão preservada:** sem novo banco de dados ou arquivo histórico independente nesta etapa.


### Em desenvolvimento — qualidade comprovada das fontes

- [x] Auditar a execução real do GitHub Actions: Open-Meteo, METAR, INMET avisos
  e CPTEC funcionaram; Defesa Civil SC não respondeu; INMET/Cemaden sem token.
- [x] Implementar **consulta complementar ao arquivo anual oficial INMET**,
  com limites para ZIP, classificação **observado porém atrasado**, completude
  horária e controle de frequência. **Validar download real após o merge.**
- [x] Melhorar fallback, diagnóstico e UTC da Defesa Civil SC, sempre sem
  classificar notícias como alertas com vigência comprovada.
- [x] Comparação explícita de máximas CPTEC x Open-Meteo por dia, sem misturar
  áreas de referência ou tratar diferenças como perigo.
- [ ] Confirmar no GitHub Actions quais endpoints respondem após o PR.
- [ ] Buscar API oficialmente autorizada para chuva instrumental recente:
  Cemaden/JWT, INMET autorizado e Epagri/Ciram.
- [ ] Construir consulta hidrológica e radar apenas quando licença, estabilidade
  e cobertura territorial estiverem verificadas.

**Armazenamento histórico externo permanece adiado por decisão do projeto.**


### Etapa 8 — qualidade e rede regional (2026-11)

- [x] Retrocompatibilidade do catálogo INMET automático sem `network_type`.
- [x] Descoberta independente de estações próximas a partir dos metadados de CSV do ZIP anual INMET, com validação de código, localização e cobertura.
- [x] Integração do cadastro GIS oficial da Epagri/SC (metadados, não medições), com cache e painel por município.
- [x] Integração RSS de avisos meteorológicos Epagri/Ciram (publicações, janelas e abrangências explicitadas quando disponíveis).
- [x] Testes sintéticos e diagnósticos de conectividade adicionados.
- [ ] Provar leitura integral de estações reais do ZIP no GitHub Actions após merge; identificar estado e cobertura.
- [ ] Provar comunicação dos novos endpoints Epagri no runner do GitHub; monitorar disponibilidade e mudanças de esquema.
- [ ] Encontrar interface oficial de boletins da Defesa Civil SC efetivamente acessível pelo runner sem burla de proteção.
- [ ] Obter autorização real das APIs INMET recente/Cemaden ou outra fonte instrumental para chuva quase em tempo real.

Nenhuma alteração foi feita no armazenamento histórico externo, conforme decisão do projeto.

### Integrações e qualidade regional (V9)
- [x] Distinguir a estação mais próxima da estação mais próxima com medição pluviométrica diária completa (24/24 horas), exibindo distâncias e defasagem.
- [x] Cruzamento cauteloso entre chuva de estação INMET e estimativa em grade NASA apenas no mesmo dia UTC, com proibição de índices falsos de precisão.
- [x] Conector independente para boletins editoriais de cinco e dez dias Epagri/Ciram, com metadados de origem e sem confundir com alertas.
- [x] Link explícito para dados horários públicos Epagri/Ciram, que requerem cadastro e condições de uso.
- [ ] Validar a nova categoria RSS Epagri/Ciram no runner GitHub e na primeira execução real de Pages.
- [ ] Confirmar integração e cobertura efetiva das estações Epagri/Ciram via acesso autorizado, sem credenciais expostas.
- [ ] Resolver indisponibilidade de canais automatizados da Defesa Civil SC; continuar priorizando INMET e avisos Epagri já verificados.

### Etapa de cobertura regional e sensores Cemaden

- [x] Acrescentar Blumenau, Itajaí e Jaraguá do Sul (dez cidades) para previsões de modelo e consultas regionais.
- [x] Integrar catálogo de tipos de sensores PED e dados instrumentais recentes de Santa Catarina, separados dos acumulados pluviométricos por município.
- [x] Compartilhar a sessão SGAA e aplicar limite de chamadas entre os dois coletores Cemaden.
- [x] Reassociar estações de arquivo anual INMET às novas localidades usando cache.
- [ ] Validar disponibilidade real de temperatura, vazão e outros sensores no ambiente GitHub Actions com a conta autorizada, após o merge.
- [ ] Avaliar consulta mais frequente de precipitação sem vender como alerta em tempo real; primeiro comprovar limites e confiabilidade das medições.
