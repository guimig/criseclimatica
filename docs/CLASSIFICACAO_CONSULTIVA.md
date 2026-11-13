# Classificação consultiva e inicial objetiva

Método `araquari-risk-v4` (13/11/2026). As regras adicionais e o papel de cada fonte estão em [Aproveitamento das fontes e contingência](APROVEITAMENTO_DAS_FONTES.md). Referência de categorias: PN 13/2026, art. 6º. Esta é a classificação calculada pelo aplicativo; `official_level` permanece nulo. A decisão institucional sobre atividades não é automatizada.

## O que aparece na inicial

1. Nível consultivo, motivo em uma frase e escala dos seis níveis.
2. Três comparações: chuva observada/prevista, rajada observada/máxima prevista e temperatura observada/máxima prevista.
3. Uma frase de previsão para o turno atual, quando disponível.
4. Dois gráficos: observações e previsão, com período e controles independentes.
5. Botão **Entenda a classificação de riscos**: abre uma explicação do nível atual, das evidências e dos seis níveis, sem sair da inicial.
6. Avisos positivos Epagri/Ciram e INMET em blocos recolhidos por padrão, com título, abrangência, período, resumo e acesso ao anúncio completo.

A inicial mantém somente os avisos positivos em blocos por instituto. Ausência de avisos, falhas de consulta e estados negativos são detalhados em **Dados e fontes**, juntamente com estações, métodos, histórico e comparação de modelos. Os avisos do entorno são identificados sem afirmar inclusão municipal de Araquari; janelas não conciliadas aparecem como **validade a confirmar**, sem declaração de vigência. Avisos encerrados ou consultas vencidas não permanecem na inicial. Avisos preservados de consulta anterior só aparecem com janela verificada ainda válida e indicação da origem anterior. Abrir ou fechar um bloco não altera a classificação. Os indicadores levam aos gráficos correspondentes. Uma temperatura diária INMET usada por falta de série horária é identificada como diária e leva à comparação detalhada.

## Critérios dos níveis

| Categoria | Regra operacional implementada |
| --- | --- |
| Verde — Normalidade | Cobertura atual de chuva local em 1 h e 24 h; previsão horária completa de 24 h para chuva, vento e rajadas **ou caminho qualitativo INMET descrito abaixo**; consulta atual de ao menos um instituto de avisos; nenhum sinal de atenção ou aviso positivo pendente aplicável. Ausência de aviso, isoladamente, não basta |
| Azul — Preparação | Aviso com território e janela aplicáveis e evento explicitado para sete dias ou mais. O prazo considera o início do evento, não a coleta |
| Amarelo — Atenção | Referência quantitativa de chuva/vento atingida; aviso aplicável; previsão municipal INMET/CPTEC ou publicação regional datada com fenômeno de atenção nas próximas 24 h; ou aviso municipal positivo com validade ainda não conciliada. Um intervalo aproximado com chuva elevada pode justificar atenção, mas não uma coincidência severa |
| Laranja — Alerta | Texto de aviso aplicável indica risco alto/alta probabilidade; ou observação e previsão atingem faixas intermediárias/superiores na mesma variável e em períodos compatíveis |
| Vermelho — Alerta máximo | Texto de aviso válido explicita perigo concreto, tempestade severa iminente ou ameaça à vida. Não é atribuído por um pico numérico isolado |
| Roxo — Calamidade | A norma exige desastre prolongado, danos/prejuízos ou declaração aplicável. Esta versão não dispõe de verificação automática desses elementos e não produz roxo a partir dos sensores |

Se nenhuma evidência válida permite atribuir nível, aparece **Sem classificação**, com motivo curto. Trata-se de falha de cobertura, não de um sétimo nível. A lista dos seis níveis permanece visível.

Os critérios qualitativos da portaria não contêm a tabela numérica a seguir. Os limites numéricos são referências auxiliares operacionais do aplicativo, não regras atribuídas à norma.

## Referências quantitativas

A função consolidada `objective_analysis.band()` permanece a fonte dos limites:

| Variável | Faixa potencial | Faixa intermediária | Faixa superior |
| --- | --- | --- | --- |
| Chuva em 1 h | 20 ≤ valor < 30 mm | 30 ≤ valor ≤ 60 mm | >60 mm |
| Vento ou rajada, separadamente | 40 ≤ valor < 60 km/h | 60 ≤ valor ≤ 100 km/h | >100 km/h |
| Acumulado móvel de 24 h | — | 50 ≤ valor ≤ 100 mm | >100 mm |

Uma faixa positiva sustenta **atenção consultiva**. O acumulado de 24 h não estabelece sozinho laranja. Para laranja por números, observação e modelo devem estar em faixas intermediárias/superiores, na mesma variável e com diferença de até 60 minutos. Chuva exige também sobreposição dos intervalos. A comparação usa o horário da medição, não o maior pico de outro momento das próximas 24 h.

Leituras IFC com intervalo original de vento ainda não verificado não sustentam a coincidência severa. Diferenças aproximadas de contador de chuva não geram laranja. Nenhuma média dilui um extremo válido. Temperatura é exibida e comparada; não recebe limites de risco inventados sem referência climatológica adequada. A normalidade calculada descreve os critérios monitorados de chuva/vento/avisos, não uma garantia universal de segurança.

## Fontes e território

- Rainha, Porto Grande, Centro e IFC Araquari têm peso igual nas variáveis comparáveis.
- Chuva diária IFC não é convertida diretamente em acumulado móvel de 24 h.
- Observações e previsões permanecem identificadas; previsão não vira medição.
- A previsão horária selecionada pode ser substituída por variável por outro produto completo, conforme o método multifontes.
- Avisos Epagri/Ciram e INMET têm igual relevância na leitura meteorológica. O mesmo reconhecedor de expressões qualitativas é aplicado ao texto dos avisos disponíveis. Não há conversão automática da cor do instituto em nível IFC.
- Avisos INMET municipais exigem correspondência exata de Araquari. Avisos apenas de outros municípios não são apresentados como locais.
- METAR até 25 km permanece contexto regional identificado; seus valores não entram na média das quatro estações.
- Epagri/Ciram continua identificada como referência prevista na norma. O resultado antigo de correspondência é preservado para auditoria, mas não substitui a classificação multifontes atual na tela.

## Aviso com prazo não conciliado

Foi reproduzido o caso da captura: a consulta INMET retornava aviso de tempestade para Araquari com início e fim normalizados iguais, enquanto o texto da fonte apresentava horários separados. Esse aviso não podia ser chamado de vigente com janela verificada; tampouco deveria desaparecer da interpretação e permitir um texto genérico de tranquilidade.

O algoritmo atribui **Atenção**, com a frase **INMET: Tempestade; validade a confirmar.** A classificação depende da consulta positiva recente e da abrangência municipal, sem inventar fuso, horários ou severidade maior. Avisos com data final informada anterior ao dia local são excluídos desse caminho, evitando atenção permanente por registro antigo. Uma consulta falha não é apresentada como consulta positiva nova.

## Atualidade e precedência

Cada candidato conserva evidências, origem e vencimento. A apresentação escolhe o maior nível entre candidatos ainda válidos. A normalidade vence com a primeira referência necessária que expirar; ela não é renovada pela atualização do navegador.

- Chuva de 1 h: até uma hora da medição.
- Chuva de 24 h: até seis horas.
- Campos IFC: até 90 minutos, conforme o produto instrumental.
- METAR elegível: até duas horas.
- Previsão horária: até oito horas, limitada também pelo relógio original da referência.
- Consulta de avisos: até seis horas, limitada pelo fim do aviso quando conhecido.
- Azul: também limitado pelo instante em que a antecedência deixa de ser sete dias.

Falta de uma fonte não elimina os candidatos sustentados pelas outras. Fonte sem dados ou leitura vencida não vira zero. A normalidade exige cobertura explícita, enquanto um sinal positivo válido pode sustentar atenção com cobertura parcial.

## Contingência das previsões horárias

A seleção consulta primeiro os produtos da coleta atual, na ordem operacional já existente. Se uma variável não tem produto completo atual, consulta `model_forecast_history.json`, da publicação mais recente para a mais antiga. Recupera uma **série inteira por variável**, nunca horas combinadas de rodadas diferentes. Produtos completos atuais têm precedência sobre qualquer produto recuperado.

São obrigatórios: Araquari, coleta original anterior à publicação arquivada, publicação arquivada não futura, coleta e referência originais dentro de oito horas e os 24 horários válidos da janela requerida. O vencimento é `min(collected_at, reference_at quando existente) + 8 h`; no instante do vencimento o produto deixa de participar. Uma falha repetida não renova esses relógios. Identificadores, pontos solicitados/grade e referência permanecem originais. `retained_previous` e `archive_saved_at` registram a recuperação em `selected_forecast.sources_by_variable` e no histórico de cada análise.

O arquivo de comparação conserva o resultado real das consultas atuais, inclusive falhas. Previsões recuperadas não são gravadas como uma rodada nova no arquivo de modelos. O arquivo passa a conservar também o ponto da hora corrente, necessário para vento/temperatura; a chuva continua usando somente os intervalos terminados em T+1…T+24. Nenhum ponto de previsão é convertido em observação. Sobreposição chuva/rajada exige mesmo produto **e mesmos relógios originais**, evitando confundir duas rodadas de um mesmo modelo.

## Participação qualitativa do INMET

A previsão municipal é uma evidência própria, além dos avisos INMET. O adaptador valida Araquari/SC e IBGE 4201307. A análise usa os dias normalizados de `synthesis.forecast_context`, com consulta original há menos de seis horas e `valid_until` ainda futuro. Uma recuperação INMET conserva a consulta original e seu prazo; `issued_at` continua nulo porque a emissão completa não foi fornecida.

A [descrição oficial do serviço](https://portal.inmet.gov.br/servicos/previs%C3%A3o-do-tempo) informa turnos nas primeiras 48 h e previsão diária até cinco dias. Para organizar a análise, o aplicativo usa manhã 00–12 h, tarde 12–18 h, noite 18–24 h e dia 00–24 h, em **America/Sao_Paulo**. São divisões operacionais, não horários exatos de início/fim do fenômeno fornecidos pelo instituto. Não há interpolação horária. Só participam períodos que interceptam `[agora, agora + 24 h)`. Períodos encerrados e fenômenos posteriores a essa janela não geram atenção atual por este caminho. O vencimento de cada evidência é o menor entre consulta + 6 h, prazo original e fim do período.

| Conteúdo reconhecido | Participação |
| --- | --- |
| Trovoada, tempestade, temporal, granizo, chuva/pancadas fortes ou intensas, vento forte ou intenso | Atenção consultiva; texto, data e turno originais são registrados. Não gera laranja/vermelho nem coincidência severa com sensor |
| Céu claro, claro, poucas/muitas nuvens, parcialmente nublado, nublado ou encoberto, inclusive com possibilidade de chuva isolada, chuvisco, névoa ou nevoeiro; vento explicitamente fraco/calmo | Pode fornecer cobertura qualitativa para Normalidade, junto aos demais requisitos abaixo |
| Texto desconhecido, negado, intensidade ausente ou vento somente moderado/rajadas sem intensidade | Não certifica condições sem atenção e não sustenta Normalidade pelo caminho qualitativo. O original permanece acessível |

A versão v4 amplia essa interpretação conforme [APROVEITAMENTO_DAS_FONTES.md](APROVEITAMENTO_DAS_FONTES.md), preservando os números INMET e incluindo CPTEC, boletins elegíveis e referências regionais identificadas. O reconhecedor é determinístico, com vocabulário explícito em `inmet_periods.py`, sem IA ou nota de confiança. Não transforma “fracos” em km/h, texto de chuva em mm, nem extremos diários em temperaturas de cada turno. As temperaturas não ganham novos limiares de risco.

### Normalidade com previsão diária/por turno

A cobertura qualitativa precisa ser contínua nas próximas 24 h: todos os turnos intersectados, ou um produto diário completo para o trecho correspondente. Um turno ausente, duplicado/conflitante ou desconhecido invalida essa alternativa. Por variável, a previsão horária completa continua preferida; o caminho INMET pode substituir apenas o requisito indisponível:

- Chuva: cobertura qualitativa reconhecida nas próximas 24 h, **mais** observações locais válidas de chuva em 1 h e 24 h, já obrigatórias.
- Vento: cobertura INMET com vento explicitamente fraco/calmo em toda a janela, **mais** medição local válida de vento para substituir a previsão horária de vento.
- Rajadas: a mesma cobertura textual de vento, **mais** medição local válida de rajadas. Isso não equivale a uma máxima de rajadas prevista; a resolução fica identificada como qualitativa.
- Consulta atual de avisos de ao menos um instituto, ausência de sinal positivo nas evidências monitoradas e ausência de pendência Epagri aplicável continuam obrigatórias.

Normalidade calculada significa **sem sinais de atenção nas referências monitoradas**, não comprovação de que todos os futuros valores horários ficarão abaixo dos limites. Não nasce de ausência de aviso. Sem as medições ou a cobertura descritas, permanece Sem classificação, salvo outra evidência positiva válida que sustente um nível. Avisos ou medições de maior nível mantêm precedência; previsões tranquilas não os rebaixam.

A inicial identifica discretamente **Consultivo · previsão por turnos** quando a cobertura usa essa alternativa. O gráfico identifica **consulta anterior** quando usa série recuperada. Os detalhes mostram resolução, prazo e evidências de cada requisito. Não são acrescentados blocos por fonte na inicial. `risk_classification.coverage` informa a resolução e as variáveis horárias recuperadas, separadamente do nível. O botão de explicação e os avisos positivos recolhíveis permanecem ativos.

O campo legado `risk_criteria: false` e o identificador legado do produto bruto INMET permanecem por compatibilidade dos consumidores: o produto bruto não é um critério numérico da norma nem determina nível diretamente. `consultative_role: qualitative_daily_or_period_evidence` explicita seu uso. A interpretação agora ocorre na camada consultiva versionada v3 e ampliada na v4, sem modificar `assessment.official_level` ou a correspondência normativa anterior.

## Rastreabilidade e histórico

`data/dashboard.json → risk_classification` contém nível, nome, motivo, versão, candidatos e requisitos de normalidade. A mesma classificação é incluída em `synthesis.risk_classification` para a página detalhada. `assessment.official_level` e `risk_classification.official_level` permanecem nulos.

`src/observatorio/risk_classification.py` calcula o resultado. `web/weather-synthesis.js:riskLevel()` reavalia apenas validade e precedência dos candidatos publicados; não inventa regras meteorológicas no navegador. A validação do artefato confere que o nível corresponde às evidências.

O histórico de episódios passa a registrar a classificação e a versão novas, preservando os episódios anteriores e iniciando transição metodológica. O histórico multifontes guarda também o produto de classificação de cada coleta. Não há reclassificação retroativa.

## Validação e reversão

Testes em `test_forecast_contingency.py` reproduzem falha total dos modelos horários, recuperação sem renovação de prazo, prioridade da coleta atual, integridade de rodadas, expiração exata, INMET diário/por turno, textos desconhecidos, falta de medição/consulta e atenção qualitativa. Os demais testes cobrem normalidade com cobertura e sua expiração, ausência de dados, estações com pesos iguais, extremos, avisos com janela válida/pendente, empate/precedência, preparação, coincidência severa e proibição de calamidade por números. O cenário da captura é reproduzido com os dados publicados. Testes Chromium verificam a inicial reduzida, detalhes, gráficos, temas, 320–1440 px e passagem entre Atenção e Normalidade.

Reversão por revert do commit. Não há migração de banco nem escrita nos serviços meteorológicos. Coletores, atualização de 30 minutos, arquivos de origem e publicação atômica foram preservados.
