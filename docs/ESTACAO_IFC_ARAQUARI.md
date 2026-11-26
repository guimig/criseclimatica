# Estação meteorológica do IFC Araquari

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


Integração implantada em 09/11/2026 para acompanhamento local. **Participa da síntese meteorológica local com peso igual às demais estações nas variáveis compatíveis; não define nível institucional. Contador diário não é equiparado ao acumulado móvel de 24 h.** A instalação, calibração e metodologia dos sensores ainda precisam de confirmação com os responsáveis pela estação.

## Acesso e coleta

- [Painel público da estação](https://mytb.fabricadesoftware.ifc.edu.br/dashboard/421b5150-dcf9-11f1-87e4-35fbd30ce4f4?publicId=f2146870-34a4-11f0-ac33-dfcfe81f8a64), hospedado no ThingsBoard da Fábrica de Software do IFC.
- Dispositivo observado no painel: `948e1e60-5611-11f0-ac33-dfcfe81f8a64`.
- `src/observatorio/campus_station.py` abre uma sessão pública em `POST /api/auth/login/public`, usando somente o `publicId` já presente no link público. Não exige senha administrativa, token do dispositivo, alteração de permissões ou credencial nova.
- O JWT público é temporário, permanece somente na memória do coletor e nunca é publicado, registrado ou enviado ao navegador. As chamadas seguintes são exclusivamente de leitura de telemetria desse dispositivo.
- A coleta acompanha o workflow existente: alvo de 30 minutos durante as 24 horas, com agendador externo e reconciliação do GitHub Actions. Não altera o agendamento nem a cadência de transmissão da estação.
- Quatro requisições por coleta: sessão pública, últimas leituras dentro de uma janela de 24 horas, histórico AVG e histórico MAX. Timeout de 12 segundos por requisição, resposta limitada a 600 kB e sem seguir redirecionamentos. Não requer dependência nova.
- A indisponibilidade da estação não interrompe as outras fontes. A fonte isolada também não autoriza publicar quando todas as fontes operacionais anteriores falham.

## Problema encontrado e correção preventiva

Na verificação de 09/11/2026, o endpoint sem intervalo que retorna o último valor devolveu registros datados de **2096**, inclusive uma temperatura `nan`. Existem, simultaneamente, observações de 2026 no histórico. Alguns cartões do painel de origem refletem os registros futuros e outros exibem a série corrente.

O coletor **não usa a consulta ilimitada de último valor**. Toda consulta fixa `startTs` e `endTs`, em UTC, e ainda rejeita timestamps fora da janela, datas futuras, valores não finitos, booleanos e valores fora das faixas de plausibilidade. Conflitos no mesmo sensor/instante são descartados. Não se corrige artificialmente o relógio dos registros da fonte.

## Campos publicados

As unidades abaixo foram conferidas na configuração pública dos widgets. A confirmação do significado operacional do sensor e de sua calibração é uma etapa diferente.

| Chave | Unidade | Série gráfica de 5 minutos | Limite de interpretação |
| --- | --- | --- | --- |
| `temperature` | °C | Média das leituras disponíveis | Temperatura do sensor instalado; exposição ainda não verificada. |
| `humidity` | % | Média | Umidade relativa; valores fora de 0–100% são rejeitados. |
| `pressure` | hPa | Média | Não se presume correção ao nível do mar. |
| `rain_daily` | mm | Máximo | Contador diário informado, sem conversão em acumulado móvel de 24 h. |
| `rain_intensity` | mm/h | Máximo | Intensidade informada; não se integra como volume sem metodologia validada. |
| `wind_avg` | km/h | Média | Média do campo já chamado de vento médio pela fonte; intervalo original a confirmar. |
| `wind_gust` | km/h | Máximo | Máximo do campo de rajada, sem média de picos; intervalo original a confirmar. |
| `wind_direction_deg` | graus | Somente última leitura | Não se faz média aritmética de direções circulares. |

Não são integrados: qualidade do ar, resistência/voltagem do sensor de gás, temperatura interna do ESP32, bateria ou informações de firmware. O painel de origem apresentou percentual inválido de bateria, e os índices de qualidade do ar não têm metodologia confirmada nesta integração.

## Arquivo, interface e validade

`data/campus_station.json` publica somente os campos permitidos. Contém identidade da fonte, horário da consulta, janela consultada, valores pontuais com seus horários, séries de até 300 pontos por variável e contagem de rejeições/conflitos. `publication_at` identifica o artefato do site, sem renovar os horários das medições. Não mistura snapshots de publicações distintas nem usa dados anteriores como se fossem uma coleta nova.

Uma medição é recente até 90 minutos após seu horário original, independentemente da idade da publicação. Leituras antigas continuam identificadas como antigas; ausência de dado nunca vira zero. Cada variável tem seu próprio horário. Os estados distinguem fonte indisponível, sem dados, histórico antigo, fonte com leituras recentes e simulação offline.

A seção **Observações no campus** aparece na inicial e em **Dados e fontes → Medições**, sempre identificada como IFC Araquari mesmo quando outro município está selecionado. O gráfico apresenta uma variável por vez, histórico consultado das últimas 24 horas, quantidade de intervalos disponíveis e leitura por mouse/toque ou teclado. Lacunas maiores que 12 minutos não são interpoladas. Quedas do contador diário interrompem a linha; não são transformadas em chuva negativa.

Atualização da interface: consulta da identidade publicada a cada minuto quando visível, recuperação após falha de rede, retorno à aba, reconexão e botão Atualizar. Um erro preserva a leitura anterior com os horários originais. A classificação principal conserva sua própria lógica de atualização e validade.

## Limitações e próximos critérios de habilitação

Antes de considerar esta estação como entrada da classificação: confirmar localização e exposição dos instrumentos, calibração, frequência/intervalo das rajadas, fuso e reinicializações dos contadores, disponibilidade histórica e divergências com estações próximas em períodos equivalentes. Chuva diária, mensal e total podem coincidir sem que isso, por si só, demonstre defeito; a rotina de reinício precisa ser documentada. Não se calculam acumulados móveis pela soma dos contadores.

A API pública foi testada diretamente; sua continuidade depende de a instituição manter o painel/dispositivo acessíveis. A interface do nosso site não consulta o servidor do IFC diretamente: recebe o JSON publicado pelo workflow, evitando dependência de CORS e sessões no navegador.

## Validação e reversão

- `tests/test_campus_station.py`: consulta delimitada, datas de 2096, NaN/infinito, conflitos, valores ausentes, zeros reais, falha de rede, horários antigos, unidades e isolamento da classificação.
- `tests/campus_station.cjs`: contrato público do frontend, valores inválidos, data futura e identidade da publicação.
- `tests/ui_campus_station.py`: Chromium nas duas páginas, 320/390/1440 px, temas, seleção de variável, teclado/hover e leituras antigas.
- O build offline não consulta a estação. A validação do artefato verifica esquema, unidades, intervalos, valores, limite das séries e proibição de `risk_criteria: true`.

Reversão: reverter o commit desta integração, removendo seu coletor, JSON e seção compartilhada. Não há migração de banco de dados, escrita no ThingsBoard ou alteração nos registros originais.

## Evolução do aproveitamento instrumental (26/11/2026)

O novo link público é o informado em 26/11; o dispositivo conhecido não é trocado automaticamente. A sondagem pública do CI consulta os nomes das chaves e, quando acessível, os campos configurados no dashboard, sem divulgar JWT nem ativar sensores não validados. São até cinco chamadas por coleta (a direção tem consulta bruta limitada a 300 pontos); falhas de um grupo de histórico não invalidam a leitura dos demais.

O histórico instrumental separado permanece em `multisource_history.json` e é publicado também na síntese e em `campus_station.json`. Até 600 registros por variável, sete dias, resolução de 5 min no trecho recente e resumos de 30 min no trecho antigo, com mínimo/máximo e quantidade de intervalos. Não aumenta a cadência de coleta, não soma acumulados móveis e não interpola lacunas. O gráfico detalhado permite 24 h, 72 h e sete dias. A direção é amostrada, nunca recebe média aritmética de graus; a distribuição usa somente pares com vento não nulo e a cobertura é explícita. As novas séries não representam extremos brutos de temperatura, mas médias instrumentais de 5 min.

O maior valor válido de vento ou rajada da última hora já coletado pode fundamentar Atenção, sem duplicar estações nem permitir coincidência severa de intervalo não verificado. Os acumulados móveis de 1 h são aproximações do contador no mesmo dia, com intervalos consecutivos; as janelas de 1–24 h exibem incrementos parciais e minutos cobertos, sem afirmar total através de reinício. Não se habilitam acumulados de 24–72 h completos sem verificar o contador total, o fuso e os reinícios. Umidade/temperatura pareadas permitem ponto de orvalho e índice de calor estimado (T ≥ 26,7 °C e UR ≥ 40%; sem avaliação ocupacional); tendência de pressão em 3 h e direção são contexto, não novos critérios de risco. A calibração, exposição, intervalo original e identidade de eventuais novos dispositivos continuam pendentes de confirmação. A validação de previsões por horizonte requer séries equivalentes e permanece etapa futura, sem atribuição automática de pesos.

Os resumos antigos de contador e chuva móvel mostram o último término efetivamente disponível, com extrema e cobertura registrados à parte; máximos de rajada e intensidade são preservados. Uma consulta histórica bem-sucedida substitui suas amostras no período; quando falha, as anteriores permanecem com seus horários originais. Janelas de chuva com qualquer intervalo de 5 min ausente não são completas.

## Contador total e validade instrumental (sondagem real de 26/11/2026)

O dashboard público declara `rain_total` em mm. A consulta bruta de 6 h recuperou 300 amostras do total (0,56 a 0,84 mm) e diário (0 a 0,28 mm), com concordância de uma variação de 0,28 mm e cadência dominante de 5 s; `rain_increment`, `bme_cal_ok` e `dew_point` não retornaram amostras. Não se presume que esses campos estejam disponíveis. A tentativa de consulta agregada de 72 h falhou; portanto a coleta usa janelas de 6 h sobrepostas, retendo no máximo 73 h de incrementos conferidos (878 pontos, sem telemetria bruta). A cobertura de 24/48/72 h cresce com as coletas. São exigidos contador monotônico (MAX/MIN), pelo menos duas amostras de total por bloco, contagem correspondente do contador de suspeitas, ausência de mudança de suspeitas, ausência de lacunas, concordância com o diário no mesmo dia quando disponível e, quando existir fluxo completo de incrementos, comparação com sua soma. Sem suspeitas disponíveis, sem reconstrução. Cada janela tem valor parcial, minutos cobertos e horário; apenas janelas completas alimentam as estatísticas de 1/24 h, os gráficos e o contexto antecedente de 3–72 h. Todas permanecem aproximações de 5 min, sem novas condições de Normalidade ou Alerta. Uma consulta malsucedida não altera o horário da referência anterior; uma lacuna identificada no trecho consultado invalida esse trecho.

As flags `humidity_valid`, `bme_stale`, `bme_cal_ok` e `bme_consec_fails` são consultadas com limite de 1500 amostras por chave e avaliadas no mesmo bloco de 5 min. Flags explicitamente negativas removem somente os campos termohigrométricos afetados. A memória limitada a 25 h evita reintroduzir leituras antes rejeitadas quando a flag sai da janela bruta. A falta de flag não significa validação. A indicação de calibração é do firmware, não certificação metrológica. Vento e pluviômetro permanecem independentes. O painel detalhado expõe as limitações; nenhuma frequência de coleta foi alterada.

A coleta primária usa leituras brutas de 1 h (máx. 1000 por chave), pares de total/suspeitas com horários idênticos e amostras em ambos os limites de cada intervalo, tolerância de no máximo 30 s entre amostras ou limites. Não interpola faltas. A consulta agregada de 6 h é alternativa quando a leitura bruta está indisponível, e os 73 h de arquivo são construídos progressivamente. A ausência de `rain_increment` nunca é substituída por zero; o confronto com seus valores é usado quando o fluxo existe. O arquivo mantém apenas diferenças aceitas, não as milhares de leituras brutas. Valores estimados pelo antigo contador diário não preenchem lacunas de um trecho de histórico com total validado.
