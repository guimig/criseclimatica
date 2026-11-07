# Síntese consultiva com foco em Araquari

> Registro da primeira implementação. A referência ao protocolo local foi substituída pelas PN 13/2026 e PN 14/2026; o painel e a metodologia atuais estão em [Painel Araquari](PAINEL_ARAQUARI_PN13_PN14.md).

O IFC Campus Araquari está no município de Araquari. A síntese principal permanece nessa localidade, mesmo durante a consulta aos painéis de outro município. As demais localidades são contexto complementar; suas previsões não substituem dados ausentes de Araquari. A referência de coordenadas continua sendo o ponto municipal já configurado, sem alegação de medição dentro do campus.

## Produtos e métodos

O processamento em `src/observatorio/analysis.py` gera `data/analysis.json`. Não há nota de risco, decisão automática, cadastro de estruturas ou serviço adicional de IA.

| Pergunta | Dados e método | Condição para apresentar | Limitação e sugestão consultiva |
| --- | --- | --- | --- |
| Quanto choveu anteriormente? | Cemaden por IBGE exato; acumulados individuais de 1–72 h, sem soma entre estações ou janelas | Consulta e leitura dentro de 6 h; números válidos | Leitura pontual, sem média municipal. Considerar antecedentes junto à previsão e às condições locais |
| Quando a chuva prevista se concentra? | Open-Meteo; maiores somas em 3 e 6 intervalos consecutivos dentro da janela identificada de 24 h | Todos os 24 intervalos válidos; duplicata idêntica é consolidada e conflito invalida a hora | Janela começa na hora UTC corrente; chuva em T refere-se à hora anterior. Avaliar horários de atividades externas; não comprova segurança de deslocamento |
| Quando ocorrem os maiores ventos? | Máximos horários de vento e rajada, separadamente | 24 referências únicas válidas por variável | Não são limites institucionais de perigo. Considerar horários de maior exposição |
| O calor previsto persiste? | Contagem de referências horárias ≥30 °C e maior sequência consecutiva | 24 temperaturas válidas | 30 °C é referência descritiva exploratória, sem classe oficial de perigo. Contagem de referências não prova temperatura continuamente acima do valor. Avaliar horários de menor exposição; não equivale a sensação térmica |
| Chuva e rajada coincidem? | Chuva da hora que começa no instante da maior rajada | Chuva completa e pico de rajada válido | Contexto horário do modelo, sem probabilidade de evento conjunto |
| Há aviso oficial para o município? | INMET por IBGE; sobreposição com a janela da previsão apenas com início/fim e fuso explícitos | Consulta recente; datas não são convertidas com fuso presumido | Aviso não confirma ocorrência. Considerar acompanhamento e eventuais ajustes; suspensão, permanência abrigada e saída são situações distintas |
| Há observação recente próxima? | METAR até 100 km e até três referências por município; sensores Cemaden de temperatura com unidade °C documentada no conjunto de proximidade existente | Idade e distância identificadas; temperatura Cemaden dentro de 3 h 20 min, METAR dentro de 6 h | Distância sempre visível. Dados de estação não são observação de todo o município |
| Duas fontes próximas têm temperaturas semelhantes? | Open-Meteo atual e METAR até 25 km, diferença de referências até 60 min | Fontes recentes, variável numérica válida | Mostrar lado a lado, sem diferença chamada erro; altitude, altura e agregação não conciliadas |
| A previsão mudou? | Comparar a publicação anterior e a atual nos mesmos 24 intervalos futuros | Ambos completos; mesma referência municipal e grade; publicação anterior de até 24 h | Diferença entre publicações não mede desempenho. Coleta não equivale à emissão do modelo; redução prevista não garante deslocamento seguro |

CPTEC e Open-Meteo diário permanecem lado a lado, sem diferença numérica enquanto os limites dos dias não forem conciliados. Open-Meteo informa dias UTC. NASA POWER, INMET anual e histórico diário de publicações continuam com sua natureza própria; nenhum deles é transformado em observação de agora. Epagri editorial e catálogos permanecem nos painéis existentes.

## Persistência limitada para revisões

`data/forecast_snapshot.json` guarda somente a última publicação, até 49 referências horárias por município, com coordenadas, grade e coleta. Não é série observada, climatologia nem arquivo de emissões de modelos. Não contém credenciais.

O build recupera esse arquivo opcionalmente do próprio Pages, com limite de 1 MB. Falha, ausência, formato incompatível ou cobertura parcial desabilitam a comparação; não significam estabilização ou melhora. Não se reaproveita uma comparação anterior durante uma falha do modelo. O histórico já existente é preservado separadamente.

## Validade e apresentação

- Síntese principal fixa em Araquari, seguida dos painéis municipais existentes.
- Evidências detalhadas e tabela regional ficam recolhidas inicialmente.
- Sugestão informa evidência, município e limitação; horários estão no respectivo resumo e nos detalhes.
- Validade máxima da síntese de 3 h, limitada também pelo vencimento das referências usadas nas sugestões. O navegador reavalia a cada minuto e ao recuperar visibilidade.
- Após vencimento, as sugestões são retiradas e as evidências permanecem identificadas como referências da publicação anterior.
- As leituras individuais próximas têm vencimento próprio explícito.
- Atualização programada a cada 3 h, sujeita a atraso do GitHub Actions e das fontes; não é monitoramento contínuo.
- Ausência de leitura, leitura zero, fonte indisponível e referência vencida têm significados distintos.

## Protocolo e parâmetros pendentes

Protocolo proposto lido como referência de relevância: A = acumulado de chuva, B = chuva intensa, C = temporal/tempestade, D = vento. Sobreposições nos limites de chuva, lacunas nos limites inteiros de vento e critérios de calor exigem validação institucional e técnica antes de qualquer classificação automática. Esta implementação não atribui níveis institucionais de perigo.

O término de um aviso não autoriza retomada. O aplicativo não conhece condições internas, danos ou condições de deslocamento. Não determina suspensão, liberação, evacuação ou permanência; as sugestões permanecem consultivas.

## Verificação

`python -m unittest discover -s tests -v` e `node tests/web_reliability.cjs` incluem regressões de ausência de Araquari, complemento regional, séries parciais, zero, duplicatas, conflitos, limites físicos, horários, unidades, revisão incompatível e vencimento de sugestões. O artefato exige foco em Araquari e classificação consultiva, além de rejeitar dados sintéticos em produção.

Os testes do coletor Cemaden agora recebem `now` explicitamente. A produção mantém o relógio real e os mesmos limites de atualidade.

A implantação deve ser confirmada pelo workflow e pela primeira publicação real. A comparação de revisões exige uma publicação posterior com estado anterior compatível; sua ausência na primeira execução é esperada.
