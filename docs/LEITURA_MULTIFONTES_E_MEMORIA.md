# Leitura multifontes, estados de acompanhamento e memória

Esta evolução complementa o painel baseado nas PN 13/2026 e 14/2026. A Epagri/Ciram permanece prioritária e o nível formal continua sob competência institucional. A avaliação deixa de depender exclusivamente de correspondências de palavras em boletins: medições e previsões recebem referências numéricas auxiliares identificadas e cruzamentos explícitos, sem votação entre fontes ou nota única de risco.

## Referências objetivas auxiliares

Exemplos oficiais consultados:

- [Aviso INMET de chuvas intensas — perigo potencial](https://avisos.inmet.gov.br/54644).
- [Aviso INMET de tempestade — grande perigo](https://avisos.inmet.gov.br/56310).
- [Tabela regional INMET de tempo severo de outubro de 2021](https://portal.inmet.gov.br/uploads/notastecnicas/Tabela-MS_tempo-severo_23-e-24-10-2021.pdf).

São referências publicadas para fenômenos de chuva/vento, não uma norma universal de níveis institucionais. A tabela histórica usa limites de vento com números inteiros; exemplos de avisos também apresentam sobreposições nos limites. A implementação define e documenta seus limites operacionais de forma conservadora, sem atribuir essas escolhas ao IFC:

| Variável | Referência potencial | Referência intermediária | Referência superior |
| --- | --- | --- | --- |
| Chuva acumulada em 1 h | ≥20 e <30 mm | ≥30 e ≤60 mm | >60 mm |
| Vento/rajada, preservados como variáveis distintas | ≥40 e <60 km/h | ≥60 e ≤100 km/h | >100 km/h |
| Acumulado móvel de 24 h | Não se usa “até 50” como limiar inferior | ≥50 e ≤100 mm | >100 mm |

O acumulado móvel de 24 h é **aproximação comparativa** da referência diária; seus limites de calendário podem ser diferentes. Não gera sozinho sugestão de nível. Temperatura não recebe classe de risco sem critérios climatológicos adequados; máximas e persistência descritiva continuam disponíveis.

## Regras integradas

1. Resultados qualitativos sustentados pela fonte prioritária são preservados; médias inferiores não os rebaixam.
2. Cada referência numérica conserva fonte, estação, valor, unidade, variável, janela e natureza observada/prevista.
3. Referência potencial isolada gera apenas contexto de atenção, sem atribuição automática de nível institucional.
4. Uma referência direta intermediária/superior pode subsidiar **sugestão de Amarelo**, claramente identificada como apoio quantitativo consultivo.
5. **Sugestão de Laranja por apoio numérico** exige referências intermediárias/superiores da mesma variável em observação e modelo, com horários próximos (até 60 min) e estação com distância verificada de até 25 km do ponto municipal. A chuva horária exige sobreposição das janelas. As posições Cemaden são conciliadas por código com o conjunto de sensores existente, quando disponíveis.
6. Comparam-se os horários da observação e do modelo correspondentes; não o máximo previsto para outro momento das próximas 24 h. Vento não é convertido em rajada, nem o inverso.
7. Coincidência contextual não comprova precisão, independência das fontes, equivalência espacial, causalidade ou impacto local. Intervalos, alturas e protocolos dos sensores ainda limitam a interpretação.
8. Vermelho não é emitido apenas por soma ou média de números; preserva-se o critério qualitativo prioritário anterior. Roxo continua exigindo verificação externa de impactos/decretos. Não há conversão automática de cor de aviso INMET em nível do IFC.
9. Referências auxiliares vencem junto às observações que as sustentam (chuva 1 h: idade máxima de 1 h; METAR: 2 h; acumulado 24 h: 6 h). A validade da sugestão é reduzida quando necessário. O vencimento do apoio de curta duração não apaga previsões ainda válidas: a interface retorna ao enquadramento prioritário ainda válido ou a Monitoramento parcial, com a limitação explícita.

A regra é identificada como `numeric-support-v1`, com integração `pn13-14-2026-multisource-v2`. Mudanças metodológicas iniciam novos episódios históricos; não reclassificam retroativamente o passado.

## Estado neutro e qualidade

A expressão genérica “Em avaliação” foi substituída por estados que descrevem o acompanhamento:

- **Monitoramento de rotina:** referências consultadas sem superação e cobertura principal suficiente. Não é nível Verde formal nem garantia de ausência de risco.
- **Monitoramento parcial:** há dados utilizáveis, mas faltam referências necessárias à leitura completa.
- **Referências de atenção:** há superação técnica, sem evidência suficiente para enquadramento específico.
- **Acompanhamento reforçado:** avisos relevantes ou nível sugerido sustentado pelas regras.

Referências vencidas retiram os indicadores atuais. Uma consulta indisponível não é tratada como ausência de avisos. A interface apresenta os trechos prioritários, os números auxiliares e as lacunas em campos próprios.

## Passado e futuro no mesmo gráfico

O modo inicial **Passado + previsão** mostra linhas contínuas para amostras observadas e tracejadas para o modelo, com a publicação como divisor. A chuva usa acumulados de **uma hora em ambos os lados**. O modo exclusivamente observado mantém a opção histórica de acumulados móveis de 24 h, identificada no título. Não há linha contínua ligando uma estação ao modelo nem somas de janelas sobrepostas.

Os antecedentes resumem valores de uma mesma referência de estação (por exemplo, mínima/máxima e quantidade de amostras de temperatura nas 24 h anteriores à publicação), sem misturar municípios ou chamar isso de média regional. Períodos ausentes não são reconstruídos; o histórico observado continua limitado a sete dias e às coletas realmente registradas.

## Memória dos estados e dos avisos

`data/assessment_history.json` conserva até 3.000 episódios de acompanhamento e 500 avisos Epagri/Ciram, por até 366 dias. O arquivo existente `notice_history.json` continua preservando avisos INMET. Após a primeira publicação, desaparecimento ou falha de recuperação do novo histórico impede sua substituição silenciosa.

Duas durações têm significados distintos:

- **Intervalo entre amostras do estado:** da primeira à última publicação registrada com o mesmo estado e versão metodológica. Não comprova permanência contínua do nível. Lacunas de coleta maiores que seis horas iniciam outro episódio.
- **Validade informada do aviso:** diferença entre início/fim fornecidos pela fonte. INMET sem fuso explícito recebe duração **nominal pelos horários da fonte**, sem inventar instantes UTC. A janela é a última revisão conhecida, não a duração observada do fenômeno.

Uma publicação repetida no mesmo instante não aumenta a quantidade de amostras. A falta de um aviso na consulta seguinte não é interpretada como cancelamento ou fim do risco. A ausência de novos registros mantém as datas originais.

## Apresentação e tema

O cabeçalho tem navegação para Visão geral, Evolução, Memória e Dados. O contraste foi reforçado com texto mais escuro, bordas mais definidas e verdes mais presentes, preservando fundos suaves. O botão de tema alterna claro/escuro, respeita inicialmente a preferência do sistema e guarda a escolha no navegador. Falha de acesso ao armazenamento local não interrompe o painel. O tema também se aplica à área detalhada.

## Validação

Testes cobrem limites e valores inválidos; rotina versus cobertura parcial; picos futuros não usados como confirmação de observações; distância/horário/variável; precedência Epagri; validade das referências; persistência idempotente; lacunas e mudanças de estado; duração nominal versus fuso explícito; seleção de tema e indisponibilidade de armazenamento; chuva horária compatível no gráfico misto.
