# Comparação de previsões em Araquari

A Open-Meteo permanece referência operacional provisória pela cobertura horária, sem comprovação de maior habilidade local. Sua seleção automática (`best_match`) pode compartilhar os modelos consultados separadamente. Não há votação entre três fontes independentes, nem média automática, ranking ou mudança nas regras institucionais.

## Produtos

- Seleção automática Open-Meteo, preservando a coleta e os indicadores existentes.
- ECMWF IFS 0,25° (`ecmwf_ifs025`) e NOAA GFS global (`ncep_gfs_global`), via Open-Meteo, somente para o ponto de Araquari. Duas chamadas adicionais de até 12 segundos por coleta; falhas isoladas não interrompem as fontes existentes. Cada resposta tem limite de 1 MB. Sem chaves adicionais.
- CPTEC/INPE, com consulta e previsão diária já existentes, destacado separadamente. Localidade e limites do dia ainda não conciliados: não entra nas faixas numéricas. Indisponibilidade ou desatualização ficam explícitas.

As duas novas respostas foram verificadas em consulta real para Araquari: precipitação, temperatura a 2 m, vento e rajada a 10 m. A disponibilidade futura continua sujeita à API. Valores nulos são lacunas por variável, sem substituição por outro modelo.

Referências: [Forecast API e definições](https://open-meteo.com/en/docs), [identificadores de modelos no esquema oficial](https://github.com/open-meteo/open-meteo/blob/main/openapi/forecast.yml), [serviço CPTEC](https://servicos.cptec.inpe.br/XML/).

## Comparabilidade

As janelas de 24 e 72 horas começam na hora UTC corrente. Para chuva, endpoints de 1 a N horas correspondem a intervalos anteriores, incluindo a hora em curso. Temperatura, vento e rajadas usam instantes de 0 a N−1 horas. Só uma série completa produz total ou máximo da janela. Duplicatas idênticas são consolidadas; conflitos e valores inválidos invalidam o horário daquela variável.

A faixa é mínimo–máximo dos totais ou máximos de janela de séries completas, nunca soma dos mínimos/máximos horários de fontes diferentes. Mostram-se os valores de cada previsão, a cobertura e a origem do maior resultado. Diferenças numéricas ficam expostas, sem limiar arbitrário de “alta confiança” ou “concordância”. Uma única série não produz faixa. A seleção automática não é substituída silenciosamente se indisponível.

As coordenadas solicitadas são iguais. As grades devolvidas podem ser distintas e são registradas; igualdade geográfica ou de resolução não é presumida. A comparação é contextual, não mede erro. Os horários mostrados são de coleta e dos alvos; emissão/rodada não está disponível nesta integração. A API entrega saída horária que pode ter sido interpolada de resolução nativa diferente.

## Interface

A inicial resume as faixas de 24 h e leva a `dados.html#model-comparison`. A seção detalhada permanece explicitamente em Araquari, mesmo ao consultar outro município. Há gráfico por variável e período, valores por modelo, horários, cobertura, CPTEC separado e métodos expansíveis. Chuva usa barras agrupadas por hora/modelo; temperatura e rajadas usam linhas, com lacunas. Toque, ponteiro e teclado permitem consultar valores.

A comparação vence três horas após a publicação. O navegador retira a leitura atual quando vence e não usa o arquivo histórico como previsão vigente. Os avisos Epagri/Ciram e os níveis do protocolo permanecem em sua camada própria.

## Arquivo por coleta

`data/model_forecast_history.json` guarda até 64 publicações por sete dias. Cada registro mantém fonte, grade, hora de coleta e alvos futuros de até 72 horas; intervalos de chuva já iniciados não são salvos. O CPTEC é preservado como contexto diário da coleta, sem declarar equivalência com os alvos horários. Não há reconstrução anterior à implantação, backtest ou cálculo de precisão.

O arquivo é recuperado da publicação anterior. Se já foi publicado e desaparecer, ou estiver inválido/inacessível, o build falha para preservar a versão anterior. O arquivo não é backup externo. A validação limita o artefato a 5 MB. Para avaliar habilidade e estimar pesos futuramente, serão necessárias observações representativas, períodos compatíveis e análise por variável/antecedência; sete dias não estabelecem climatologia ou ranking robusto.

## Validação e reversão

Testes cobrem extremos, períodos, lacunas, nulos, unidades, duplicidades, desatualização, falha isolada e repetição da gravação. Os testes de navegador verificam controles, temas, toque/teclado e larguras de celular/desktop. Builds sintéticos nunca consultam os novos modelos nem são publicáveis.

Reverter o PR remove a comparação e os ajustes visuais, sem alterar observações nem reclassificar o histórico de níveis. Preserve uma cópia do arquivo de previsões antes de uma reversão se desejar conservá-lo.
