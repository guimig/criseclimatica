# Aproveitamento das fontes e contingência — método consultivo v4

Atualização de 13/11/2026. Complementa [Classificação consultiva](CLASSIFICACAO_CONSULTIVA.md). A inicial mantém classificação, indicadores, dois gráficos e evidências positivas recolhíveis. Sem produto horário para temperatura e sem INMET diário, a máxima diária CPTEC elegível pode ocupar o indicador, identificada como diária e ligada aos detalhes; o resumo curto também pode usar essa fonte. Os novos comparativos e inventários ficam em **Dados e fontes**.

## Papel de cada produto

| Produto | Uso efetivo | Condição e limite |
| --- | --- | --- |
| Open-Meteo automático, ECMWF e GFS | Previsão numérica, faixa de divergência e sinais de todos os produtos elegíveis | Cada variável exige uma série completa de 24 h de um produto/consulta; validade original até 8 h. Compartilham provedor; não são votos independentes |
| INMET diário/turnos | **Temperaturas numéricas** preservadas em `daily_quantitative` e `risk_classification.quantitative_context`; condições e vento textual na classificação qualitativa | O texto não vira mm, km/h ou probabilidade. Extremos diários repetidos por turno não viram três previsões independentes. Não se inventou um limiar de calor/frio |
| CPTEC/INPE | Condição diária na interpretação qualitativa e temperaturas numéricas no mesmo dia civil | Localidade retornada deve ser exatamente Araquari, consulta <6 h e atualização do dia local ou anterior. Localidade apenas próxima continua no painel original; não vira previsão municipal elegível |
| Cemaden pluviometria | Chuva em 1 h e 24 h na classificação; 3, 6, 12, 48 e 72 h no contexto antecedente | Quatro estações locais mantêm peso igual quando comparáveis. Janela diferente permanece separada. Acumulados aninhados inconsistentes são excluídos da camada adicional |
| Cemaden sensores | Temperatura local confirmada e inventário das demais leituras recentes | Sensor de chuva em mm sem intervalo confirmado não vira acumulado horário; inferência de unidade não confirma período nem escala |
| Estação IFC | Medições locais, sem preferência sobre as outras estações | Mantidos prazo instrumental, diagnóstico de falha simultânea e restrições dos contadores |
| NOAA/METAR | Vento, rajadas e temperatura regionais; contingência para observação de vento/rajadas | Até 25 km do ponto municipal, leitura há menos de 2 h. Não entra na média local e não comprova condições no campus. Rajada ausente nunca é zero |
| INMET pluviometria recente | Sinais quantitativos regionais quando o acesso fornece dados elegíveis | Até 25 km do ponto municipal; última hora <1 h; total de 24 h <6 h e 24 leituras completas. Origem bruta/não homogeneizada identificada. Sem credencial ou sem leitura não há contribuição |
| Avisos Epagri e INMET | Evidência de risco, com igual relevância meteorológica | Mantidas verificação territorial, janela, vencimento e regras de recuperação; não há conversão automática da cor do instituto |
| Previsão editorial Epagri | Atenção quando texto positivo, região e período são explícitos | RSS e até dois artigos oficiais por atualização. Datas editoriais de cada seção são dias civis de Brasília, não o horário de publicação. Trechos de outras regiões não contaminam Araquari |
| Publicações Defesa Civil SC | Atenção para publicação positiva com região e janela explicitamente verificáveis; relatos afirmativos de impactos no período informado | Feed não é catálogo de alertas vigentes. Título, data de publicação ou “próximas horas” sem intervalo não bastam. “Podem ser registrados” não é impacto confirmado. Não comprova calamidade nem decreto |
| NASA POWER | Contexto histórico diário em grade | Não substitui medição atual ou vira observação de pluviômetro |
| Arquivo anual INMET | Histórico observado e comparação retrospectiva | Não substitui leitura recente |
| Cadastros INMET/Epagri/convencionais | Identificação e localização de estações | Não são medições; disponibilidade do cadastro não comprova operação da estação |
| Cobertura por localidade | Inventário derivado de fontes e variáveis | Não é outro serviço meteorológico independente |

## Previsões numéricas: seleção e sinais

O produto selecionado continua controlando os indicadores compactos e o gráfico. Além dele, cada modelo horário elegível contribui com seus próprios sinais de chuva/vento/rajada. Uma previsão de atenção não desaparece porque o primeiro modelo está abaixo da faixa. A faixa entre modelos aparece somente nos detalhes e não representa probabilidade, média ou precisão demonstrada.

A coincidência quantitativa de observação elevada e previsão compatível também examina os outros modelos completos: mesma variável, até 60 minutos, sobreposição de intervalos de chuva, ambas nas faixas intermediárias/superiores, relógios e validade originais. Um máximo previsto para outra hora não gera coincidência. Intervalo instrumental não verificado, acumulado aproximado e chuva de 24 h continuam excluídos desse caminho. A coincidência sustenta laranja consultivo; não produz vermelho ou calamidade.

A recuperação das previsões anteriores válidas permanece ativa, sem remendar horas ou renovar consulta/referência. A troca de fonte não altera o peso das estações locais.

## Previsão diária CPTEC e INMET

A legenda CPTEC foi conferida no [serviço oficial XML](https://servicos.cptec.inpe.br/XML/). `t` significa tempestade e sustenta Atenção nas próximas 24 h, quando localidade e datas são elegíveis. Códigos desconhecidos não são reinterpretados. `pn`, `ps`, `e`, `n`, `cl`, `cv`, `ci` e `ec` podem completar cobertura qualitativa de chuva sem sinal explícito de atenção. Esse produto não oferece uma rajada numérica nesta integração e não certifica vento fraco.

INMET e CPTEC podem fornecer trechos complementares da cobertura de chuva. A análise conserva a fonte de cada trecho e exige cobertura contínua de `[agora, agora+24 h)`. Qualquer evidência positiva válida tem precedência sobre um texto tranquilo de outra fonte. As divisões de turno documentadas na versão v3 continuam operacionais, sem alegação de horário exato do fenômeno.

As temperaturas numéricas do INMET continuam disponíveis na comparação e no objeto da análise. A comparação preserva dia civil de Brasília e a distinção entre extremos diários informados e extremos de 24 amostras horárias. Não se usa uma temperatura diária como medição observada, nem se reparte seu máximo entre turnos. Ausência de referência climatológica validada impede inventar uma faixa de risco térmico.

## Chuva antecedente e limite inferior de 24 h

Acumulados de 3, 6, 12, 48 e 72 h são mostrados separadamente por estação, com horários. Não há soma dessas janelas sobrepostas nem novos limites da norma.

Se o total móvel de 24 h está ausente, mas uma janela de 3, 6 ou 12 h já acumula pelo menos a referência auxiliar de atenção de 24 h existente, esse valor é um **limite inferior**, suficiente para atenção consultiva: o intervalo maior contém o menor. O valor não é publicado como total reconstruído de 24 h, não completa requisito de Normalidade e não gera coincidência severa. Exige mesmo ponto, observação válida e consistência dos acumulados disponíveis. Totais de 48/72 h não são comparados com o limite de 24 h.

## Texto editorial, abrangência e impactos

A extração de artigos limita-se ao corpo `entry-content` do domínio oficial, ignorando menus, barras laterais e scripts, com até dois artigos por produto/ciclo. Falha do artigo preserva o texto do feed e o estado da consulta; não inventa conteúdo. Somente uma região explicitamente aplicável, data/janela coerente e indicação afirmativa sustentam atenção.

Para Epagri, seções `(dd/mm)` usam o ano da publicação apenas para interpretar a data de evento explicitada; seções fora da janela de 24 h não participam. Referências ao Litoral Norte, Araquari ou faixa leste/abrangência estadual são identificadas como municipais ou regionais conforme o texto. Um trecho sobre o Oeste isoladamente não produz nível local.

Para Defesa Civil, a publicação precisa informar início/fim e região. Publicações sem janela, inclusive uma manchete com “próximas horas”, ficam nos detalhes como contexto pendente. Apenas relato afirmativo, como “foram registrados alagamentos”, pode ser identificado como impacto relatado no período; não se infere dano persistente, desastre prolongado ou decreto. Evidências da camada adicional são limitadas a Atenção, preservando os critérios mais exigentes de níveis severos existentes.

Boletins Epagri positivos elegíveis aparecem no bloco recolhível já existente, identificados como previsão editorial e com link. Publicações verificáveis de outras fontes têm acesso no botão de explicação do risco e nos detalhes, sem novos cartões permanentes na home.

## Contingência regional de vento

No caminho qualitativo de Normalidade, uma medição local é preferida. Se falta vento ou rajada local, uma leitura METAR dessa **mesma variável** pode servir como referência regional, dentro de 25 km e 2 h, junto à previsão textual de vento e aos demais requisitos. Cada campo conserva seu prazo. A interface identifica “referência regional”. Não muda o peso das quatro estações locais. Sem rajada explicitamente reportada, não há substituição por vento médio nem por zero.

A perda de uma fonte deixa disponíveis os demais sinais válidos. Isso não garante classificação em toda combinação de falhas: sem cobertura suficiente, o resultado continua parcial. Em particular, a ausência simultânea de previsão de vento e de evidência equivalente não é ocultada por uma previsão diária de chuva.

## Leitura do histórico publicado

Foi encontrado um bloqueio real na coleta das 11h30 de 13/11/2026: HTTP 503 ao ler `data/multisource_history.json`, antes de consultar as fontes meteorológicas. A recuperação agora tenta até três vezes para falhas de conexão e HTTP 429/500/502/503/504, com pausas de 1 e 2 segundos e chave de cache diferente nas repetições. Dados inválidos ou sintéticos continuam rejeitados. Se todas as tentativas falharem, o build preserva a publicação anterior; não reinicia nem apaga o histórico obrigatório. O relógio de nenhuma fonte é renovado por essas tentativas.

## Transparência, armazenamento e testes

O estado de conexão e o papel metodológico aparecem separadamente em **Estado das integrações**. Os detalhes apresentam divergência dos modelos, temperaturas diárias por fonte, chuva antecedente, publicações usadas/pendentes e sensores avaliados em seções recolhidas.

O histórico passa a guardar resumo de classificação com nível, versão e referências das evidências, evitando duplicar todo o contexto em cada amostra. A publicação atual conserva o produto completo; os históricos anteriores não são reescritos. Séries instrumentais e arquivo de previsões permanecem preservados. Publicações da camada adicional são limitadas a oito evidências por instituto e oito pendências; o histórico conserva referências sem repetir os textos completos. O limite de leitura do histórico passa a 16 MB, mantendo os limites de 6.000 registros instrumentais e 336 amostras de análise. Não se migra banco nem se escreve nas fontes externas.

`tests/test_source_evidence.py` cobre falhas, fonte alternativa, divergência e coincidência temporal, códigos/localidade CPTEC, números INMET, região errada, datas ausentes/vencidas, negação, impacto hipotético, sensor sem intervalo, limite inferior de chuva e contingência METAR. A suíte visual cobre home/detalhes, temas e telas pequenas/grandes. Um teste de falha de fontes que antes fazia consultas editoriais/modelos reais foi isolado da rede para evitar dependência externa no bloqueio de publicação.

Reversão: revert do commit. Atualização de 30 minutos e publicação atômica preservadas.
