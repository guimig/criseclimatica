# Interpretação multifontes de Araquari

> Apresentação e classificação atuais: [Classificação consultiva e inicial objetiva](CLASSIFICACAO_CONSULTIVA.md). A inicial não exibe mais blocos por fonte; a síntese detalhada e os métodos permanecem na página de dados. O texto genérico “Acompanhamento das condições locais” foi substituído pelo nível consultivo calculado.


Implementação de 11/11/2026, método `araquari-multisource-v1`. Este documento descreve a síntese meteorológica atual. As regras de correspondência normativa anteriores continuam separadas; não se atribui decisão institucional automaticamente.

## Produtos e responsabilidades

- `src/observatorio/multisource.py`: registro de estações, evidências normalizadas, estatísticas, seleção de previsões, avisos e cobertura por fenômeno.
- `src/observatorio/unit_inference.py`: hipóteses empíricas de unidades, com alternativas e limitações.
- `data/dashboard.json → synthesis`: síntese compartilhada entre inicial e detalhes; inclui evidências, fontes selecionadas e histórico gráfico local.
- `data/multisource_history.json`: amostras normalizadas e contador de chuva do IFC, até sete dias e 6.000 registros, além de até 336 avaliações com cobertura, fontes escolhidas, sinais e avisos; conflitos ficam marcados e não reaparecem silenciosamente.
- `data/model_forecast_history.json`: mantém os modelos horários já existentes e passa a guardar também o produto municipal INMET de cada coleta, quando disponível. Não reconstrói previsões anteriores à implantação.
- `web/weather-synthesis.js` e `.css`: apresentação compartilhada, validade individual e explicação. Sem consulta a provedores meteorológicos no navegador.

## Estações e pesos

| Identidade | Nome | Peso por variável compatível |
| --- | --- | --- |
| 420130701A | Rainha | 1 |
| 420130702A | Porto Grande | 1 |
| 420130704A | Centro | 1 |
| ifc-araquari | IFC Araquari | 1 |

A localização no campus não concede preferência. O mesmo instrumento não é contado duas vezes por aparecer em APIs diferentes. Identidade física, variável, horário e método identificam uma amostra. Conflitos contemporâneos não são resolvidos escolhendo o valor conveniente.

Todas as estações participam quando oferecem a variável e período requerido. As três estações Cemaden não são presumidas estações completas de temperatura ou vento. Falta de sensor não equivale a valor zero. Novas estações precisam ser cadastradas em `STATIONS`; um novo adaptador deve fornecer o mesmo contrato de evidências.

## Evidências, estatísticas e qualidade

Cada observação preserva fonte, estação, variável, unidade, valor, início/fim do intervalo, validade, método, abrangência e peso. São calculados média aritmética com pesos iguais, mediana, mínimo e máximo, com membros rastreáveis. O agrupamento exige a mesma variável/janela nominal e finais a até 30 minutos da referência mais recente. Isso é uma tolerância operacional explícita, não prova de simultaneidade perfeita.

O resumo local exibe mediana e maior leitura; detalhes incluem média e valores individuais. Uma estação gera leitura individual, não confirmação por rede. Os extremos permanecem disponíveis independentemente da média. A síntese não descarta automaticamente uma estação porque divergiu das outras.

Atualidade: chuva 1 h até uma hora; chuva 24 h até seis horas; campos IFC e temperatura local até 90 minutos; contexto METAR até duas horas e 25 km. Distância não altera os pesos das quatro estações de Araquari. METAR permanece regional e não entra na média das quatro.

A consulta real durante a implementação encontrou temperatura e umidade simultaneamente zeradas no IFC, com o mesmo horário. Esta combinação é marcada como suspeita e retirada da síntese e da apresentação instrumental correspondente. Não invalida chuva ou vento, nem elimina zeros legítimos de chuva. Os valores brutos da origem não são alterados.

### Contador de chuva do IFC

`rain_daily` continua sendo contador diário em mm. Não é somado e não é convertido diretamente em chuva móvel de 24 h. Uma diferença pode produzir um intervalo nominal de 1 h/24 h somente com extremos disponíveis, sequência monotônica, lacunas de no máximo 12 min, referência recente e sem atravessar mudança do dia civil. A série usa máximos de intervalos de cinco minutos, portanto o resultado conserva incerteza temporal de cinco minutos e **não entra nos limiares institucionais**.

Uma janela móvel de 24 h atravessa a mudança do dia: com o reinício ainda não validado, continuará indisponível para o IFC. É uma limitação do significado do produto, não prioridade inferior da estação. Para habilitá-la será necessário demonstrar a regra de reinício e a recuperação dos incrementos. Não são reconstruídos volumes perdidos em lacunas ou reinícios.

## Inferência de unidades

As unidades documentadas permanecem em `unit`. Hipóteses ficam em `unit_inference`, com status, amostras, mínimo/máximo, alternativas não descartadas e uso numérico desabilitado quando a escala não foi demonstrada.

Na consulta real examinada:

| Sensor | Evidência observada | Interpretação |
| --- | --- | --- |
| 240 — intensidade da precipitação | 210 leituras regionais, valores entre 0 e 10,36; Araquari com zeros | mm/h provável pela dimensão e magnitudes; escalas alternativas ainda não excluídas. Zeros não distinguem unidades |
| 330–360, 610–620 — umidade do solo | Valores aproximadamente 34,9–46,1 | % provável; incompatível com fração não escalada de 0–1, mas calibração e definição não confirmadas |
| 20, 260, 270 — nível | Valores aproximadamente 10,3–35,0; mínimos/máximos coerentes | m, cm, mm ou referência instrumental não podem ser distinguidos só pela magnitude |

Esses valores são evidência datada da investigação, não descrição permanente do tempo. O relatório é recalculado a cada coleta. A interface mostra a unidade provável e sua condição de inferência, sem converter o valor bruto. Chuva sensor 10 continua em mm confirmados.

Inferir uma dimensão não comprova a escala ou o intervalo. A promoção futura a cálculo exige comparação de períodos equivalentes, preferencialmente taxa integrada versus incremento do mesmo instrumento, com dados não nulos e discriminação entre hipóteses. A ausência de documentação não bloqueia investigação; evidência ambígua não é apresentada como certeza.

## Previsões: participação e substituição

A seleção é feita **por variável**, exigindo 24 referências completas e coerentes: chuva usa as 24 horas terminadas em T+1 até T+24; temperatura/vento usam T até T+23. Cada variável conserva uma série inteira de um produto; não se remendam horas de diferentes modelos. Ordem operacional: seleção automática, ECMWF IFS, NOAA GFS. Não é ranking de precisão. A substituição aparece nos indicadores e no resumo, com origem registrada.

O INMET participa diretamente do resumo diário/por turno da inicial e dos detalhes, incluindo temperaturas, condições e vento textual. Não é limitado à seção expansível. Sua ausência não invalida os modelos horários, e sua disponibilidade não cria uma série horária ou volume de chuva inexistente. CPTEC participa como contexto diário com localidade identificada; seus períodos ainda não conciliados impedem misturá-lo às faixas numéricas horárias.

A comparação INMET × Open-Meteo conserva o mesmo dia civil de Brasília, exigindo 24 amostras para extremos do modelo. Os extremos horários não são necessariamente extremos contínuos do dia. Produtos disponíveis também permanecem nas áreas detalhadas originais.

Epagri/Ciram editorial entra como contexto de boletins; não é transformada em previsão pontual quantitativa. A seleção automática e ECMWF/GFS podem compartilhar modelos e o provedor Open-Meteo: não são votos independentes nem redundância de infraestrutura. OpenWeather não tem adaptador ativo no código atual; não foi reativado sem configuração/credenciais. Nenhum provedor novo é anunciado como integrado sem adaptador e validação.

Não há média geral entre previsões, conversão de texto em quantidade, probabilidade inventada ou pesos por precisão presumida. O histórico passa a permitir avaliação futura por variável e antecedência, mas esta implantação não declara habilidade local.

## Avisos e norma

Epagri/Ciram e INMET têm peso meteorológico 1, mesmo destaque e critérios explícitos de território e validade. Avisos INMET de municípios vizinhos ficam separados de avisos que incluem Araquari; só a associação municipal exata sustenta aviso local. Avisos com janela não conciliada permanecem nos detalhes do produto, sem promoção a aviso vigente verificado na síntese.

A síntese reúne avisos aplicáveis sem votação, média de cores ou apagamento de avisos divergentes. A severidade original é exibida com a fonte. Uma referência institucional laranja/vermelha ainda válida continua visível para não rebaixar a leitura anterior na apresentação.

A correspondência normativa conserva `assessment` e os critérios documentados em `ALGORITMO_CLASSIFICACAO_NIVEIS.md`. A síntese meteorológica conserva `formal_level: null` e não transforma cor INMET em nível IFC. A decisão formal continua humana. Relevância meteorológica igual não altera o texto da norma.

A inicial mantém apenas avisos positivos. Ausências, falhas e validações pendentes permanecem nos detalhes. Quando uma consulta INMET falha, só os avisos preservados que já atendem às regras anteriores de recuperação mantêm participação, com falha e consulta anterior identificadas.

## Cobertura, validade e histórico

Chuva, vento e temperatura têm cobertura independente: observações e previsão; apenas observação; apenas previsão; indisponível. Falha de fonte/variável não suspende os outros fenômenos. Leituras vencidas não viram zero nem recebem novos horários. Cada sinal, aviso e produto tem seu próprio vencimento, reavaliado no navegador.

O atraso da publicação é sinalizado separadamente. Referências restantes continuam apenas até seu prazo individual. Se não houver dados suficientes, a interface informa cobertura parcial; não declara normalidade por ausência de aviso.

A coleta a cada 30 minutos, 24 h/dia, foi preservada. O teste de fontes operacionais agora também considera estação IFC, previsão INMET e modelos alternativos. O histórico multifontes tem recuperação validada: após primeira publicação, ausência do arquivo marcado como publicado aborta o build para preservar o histórico e o site anterior. A publicação continua atômica.

## Testes e reversão

`tests/test_multisource.py` cobre igualdade de pesos, duplicidade, extremos, unidades, intervalos, contador, reinícios, conflitos persistentes, falhas, previsão por variável e avisos. `tests/weather_synthesis.cjs` verifica apresentação, validade e separação normativa. `tests/ui_multisource.py` usa Chromium para inicial/detalhes, 390/1440 px, temas, INMET e substituição por ECMWF. As suítes anteriores continuam obrigatórias.

Reverter o commit remove esta camada e recupera a apresentação anterior. Não há migração de banco, escrita em estações ou alteração de dados de origem. Preserve os arquivos históricos antes de uma reversão que retire sua recuperação; não são backup externo.
