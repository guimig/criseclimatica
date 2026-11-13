# INMET: previsão municipal e recuperação dos avisos

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


Integração de 10/11/2026, complementar às fontes existentes. **Participa da síntese diária/por turno na inicial e nos detalhes; não altera limiares numéricos ou critérios da norma.** Avisos e previsão municipal são produtos distintos.

## Previsão municipal de Araquari

- API pública: `https://apiprevmet3.inmet.gov.br/previsao/4201307`.
- Página de referência: <https://previsao.inmet.gov.br/4201307>.
- Adaptador: `src/observatorio/inmet_forecast.py`; arquivo público separado: `data/inmet_forecast.json`, também incluído em `forecast_comparison.json` e no bloco de comparação da inicial.
- Uma consulta no ciclo existente de 30 minutos, somente para Araquari, sem chave ou senha. Timeout de 18 s e resposta limitada a 1 MB. Construções offline não fazem essa consulta.
- No produto verificado, os dois primeiros dias têm manhã/tarde/noite; os demais têm previsão diária, totalizando cinco dias. O adaptador não exige que todos os dias tenham a mesma estrutura e limita a publicação a sete dias.
- Campos permitidos: condição do tempo, mínimas/máximas de temperatura, umidade, direção e intensidade **textual** do vento. Imagens base64, ícones e demais campos não são publicados.
- O código IBGE, município Araquari e UF SC são conferidos. Valores inválidos são ausentes, nunca zero. Extremos diários repetidos entre turnos não são contados como três previsões independentes. Havendo divergência entre os extremos dos turnos, os turnos são preservados, mas não se fabrica um extremo diário para comparação.

### Comparação temporal correta

A comparação usa o mesmo **dia civil de Brasília, 00h–24h**. As mínimas/máximas do INMET são apresentadas ao lado dos extremos das **24 amostras horárias** de temperatura do Open-Meteo daquele dia. Não utiliza os agregados diários UTC do Open-Meteo nem uma janela móvel de 24 h.

Um dia com horas ausentes, valores conflitantes no mesmo instante ou modelo sem coleta recente não recebe extremos comparáveis. Os valores disponíveis podem aparecer na previsão da fonte, mas não são promovidos a uma comparação completa.

Isso é comparação contextual: extremos de amostras horárias podem diferir dos extremos diários previstos. A janela do dia corrente inclui horas já decorridas da série de modelo, que continuam sendo estimativas, não observações. Não são calculados erro de previsão, média entre fontes, voto, probabilidade, confiança ou preferência por desempenho local.

O INMET não fornece, no retorno verificado, quantidade prevista de chuva em mm ou rajadas em km/h. “Possibilidade de chuva isolada” e “ventos fracos” permanecem textos. Não há conversão em porcentagem, volume ou velocidade. Desde 13/11/2026, a previsão municipal participa da **classificação consultiva v3** pela camada qualitativa, com vocabulário, cobertura, validade e medições exigidas documentados em [CLASSIFICACAO_CONSULTIVA.md](CLASSIFICACAO_CONSULTIVA.md#participação-qualitativa-do-inmet). O produto bruto não altera a correspondência normativa anterior nem fornece limiares numéricos da norma.

### Origem, duplicidade e atualização

A [documentação do Open-Meteo](https://open-meteo.com/en/docs) descreve sua seleção de modelos e não lista o produto municipal do INMET entre seus provedores. Portanto, acrescentar esse produto não é repetir uma integração já feita. Isso não comprova independência completa entre bases meteorológicas: `best_match`, ECMWF e GFS podem compartilhar modelos, e a interface já informa que não são votos independentes.

`retrieved_at` registra a consulta bem-sucedida; `last_attempt_at`, a última tentativa. `issued_at` fica **nulo**: o campo `hora` observado na API não traz, sozinho, uma data/hora completa de emissão com fuso. Ele é preservado em `hour_as_reported`, sem inferência de fuso ou emissão.

`content_fingerprint` identifica o conteúdo normalizado e `content_first_seen_at` preserva quando esse conteúdo foi visto pela primeira vez, mesmo em consultas posteriores iguais. Isso é rastreamento da coleta, não histórico completo de rodadas do INMET nem prova do instante de emissão.

Após falha, a última previsão válida pode ser reutilizada por até seis horas desde a consulta original, marcada `cached`. Entre seis e 36 horas pode ser preservada como `stale` para auditoria, mas não é apresentada como previsão atual nem usada em comparação. Datas já passadas são retiradas. A falha não renova `retrieved_at` nem `valid_until`. Se a recuperação não for válida, publica-se `unavailable`; as outras previsões continuam independentes.

## Avisos: JSON principal, sem RSS nesta etapa

O endpoint continua `https://apiprevmet3.inmet.gov.br/avisos/ativos`, com correspondência municipal exata por IBGE. Uma falha gera **uma única nova tentativa**, após um segundo. Não há laço indefinido nem consulta simultânea ao RSS.

Se ambas falharem:

- `status` continua `unavailable` e `retrieved_at` continua nulo: não se anuncia uma consulta bem-sucedida.
- O último produto é consultado em `data/alerts.json`. Somente avisos com início/fim explícitos com fuso, intervalo coerente, fim ainda não encerrado e consulta bem-sucedida original há no máximo seis horas podem ser preservados em `retained_locations`.
- A associação por município/IBGE é conferida. Os horários, ID e revisão originais não são renovados. Falhas repetidas não estendem o prazo.
- A inicial e os detalhes identificam **consulta anterior; consulta atual falhou; revisão ou cancelamento não confirmados**. Um aviso fora do prazo deixa de aparecer como vigente, inclusive com a página aberta.
- Avisos cujo fuso ou prazo não pôde ser confirmado ficam no histórico existente, sem promoção a aviso vigente recuperado. Ausência de aviso recuperável não prova ausência de risco.
- Uma consulta posterior bem-sucedida substitui a leitura anterior, inclusive se retornar zero avisos. O histórico conserva a distinção entre ausente no feed e cancelado.

O RSS foi adiado porque compartilha o servidor com o JSON e o item inspecionado apresenta abrangência textual regional, sem a mesma estrutura municipal do JSON. Não é uma fonte independente de disponibilidade nem substituto direto da seleção territorial. Sua eventual inclusão exige verificação própria de abrangência, validade e deduplicação.

## Testes e reversão

`tests/test_inmet_municipal_forecast.py` cobre município errado, estruturas por turno/dia, ausência e conflitos, horários de Brasília, dia incompleto, recuperação sem renovação artificial, fingerprint, tentativas limitadas e avisos recuperados. Os contratos JavaScript verificam validade, dados malformados e preservação da separação entre dados brutos, análise consultiva e decisão institucional. Os testes Chromium de comparação cobrem inicial/detalhes, turnos, temas e 320–1440 px.

A validação do artefato confere a igualdade entre a previsão municipal isolada e sua cópia na comparação, identidade da publicação, esquema e proibição de inferência numérica de chuva/rajadas. Não há migração, autenticação nova, mudança no agendamento ou escrita em serviços do INMET. A reversão pode ser feita revertendo o commit desta integração.
