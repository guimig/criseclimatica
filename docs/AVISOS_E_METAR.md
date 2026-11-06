# Avisos INMET e medições METAR: escopo e confiabilidade

## Objetivo

Esta integração adiciona **dois produtos independentes** às previsões de modelo da Open-Meteo:

1. Avisos meteorológicos oficiais publicados pelo INMET para cada código municipal IBGE.
2. Observações instrumentais aeronáuticas (METAR) em aeródromos da região, publicadas via Aviation Weather Center (NOAA).

A nova camada **não** fornece acumulados de chuva medidos por pluviômetros, nem significa que existam sensores em cada município monitorado.

## Fontes e limites

| Fonte | Consulta programada | Formato | Observações |
|---|---|---|---|
| INMET avisos | `https://apiprevmet3.inmet.gov.br/avisos/ativos` | JSON `hoje`/`futuro` | Endpoint utilizado por terceiros, porém **sem contrato público de estabilidade confirmado**. Falhas geram estado `unavailable`; jamais viram “sem avisos”. |
| INMET portal | https://alertas2.inmet.gov.br/ | Visualização oficial | Conferência necessária para decisões de proteção civil. |
| Aviation Weather Center | `https://aviationweather.gov/api/data/metar?ids=SBBI%2CSBCT%2CSBFL%2CSBJV%2CSBNF%2CSSBL&format=json&hours=6` | JSON | API pública documentada; boletins geralmente horários; recomendável consultar de forma parcimoniosa. |
| Dados geográficos IBGE | https://www.ibge.gov.br/explica/codigos-dos-municipios.php | Cadastro nacional | Filtro de alertas baseado em códigos exatos de sete dígitos. |

Códigos ICAO consultados em uma chamada: `SBJV` (Joinville), `SBNF` (Navegantes), `SSBL` (Blumenau), `SBFL` (Florianópolis), `SBCT` (Afonso Pena) e `SBBI` (Bacacheri). A observação principal continua sendo a mais próxima até 100 km. Referências adicionais até 180 km aparecem individualmente; acima de 100 km são exclusivamente contexto regional. Cada aeródromo conserva horário e distância. **A distância não significa representatividade meteorológica.**

### Particularidades dos avisos do INMET

- `geocodes` e `municipios` podem ser listas ou strings CSV; o filtro identifica códigos IBGE completos, nunca apenas palavras do nome do município.
- `hoje` e `futuro` podem repetir o mesmo `id_aviso`; a revisão `id_sequencia` maior prevalece.
- Avisos encerrados, quando explicitamente marcados, não são apresentados.
- O serviço separa data e hora: **não é seguro presumir automaticamente o fuso dos campos**. Portanto, a interface apresenta a janela exatamente conforme a fonte, com explicação sobre a limitação.
- O feed pode conter avisos vigentes ou futuros; a aplicação não afirma que todos já estão ativos.
- Um retorno bem-sucedido com zero avisos é diferente de uma falha de consulta.
- Na interface, dados de aviso com mais de seis horas de idade não são exibidos como se fossem novos; a consulta deverá ser feita diretamente aos órgãos oficiais.

### Particularidades do METAR

- Boletins de aeródromo podem apresentar temperatura, vento, rajadas, direção e outras condições pontuais; podem faltar campos.
- `wspd` e `wgst` são expressos em **nós** no JSON da API; o sistema converte para km/h usando o fator 1,852.
- Um campo de rajada ausente **não** significa rajada de zero km/h.
- Boletins cuja idade exceda seis horas ou cujo horário seja inconsistente são descartados.
- METAR **não** é um pluviômetro regional e não informa diretamente o acumulado pluviométrico em mm.
- O endpoint responde com `204 No Content` quando não existem registros e impõe limites de frequência. Não há chamadas diretas do navegador, apenas do workflow Python.

## Contratos publicados

`data/alerts.json`:

- `kind`: `inmet_official_notices_by_municipality`
- `status`: `available` ou `unavailable`
- `retrieved_at`: horário da coleta confirmada, ou nulo em falha
- `locations`: avisos associados por `location_id` e `ibge_code`

`data/observations.json`:

- `kind`: `aerodrome_metar_observations_not_municipal_measurements`
- `status`: `available`, `no_recent_reports` ou `unavailable`
- `stations`: registros aeródromos recentes
- `locations`: referência à observação mais próxima dentro do limite configurado

Nos dois casos, **a indisponibilidade é explícita**. Se uma fonte secundária falhar, a previsão Open-Meteo pode continuar sendo publicada; o sistema nunca fabrica medidas ou avisos.

## Validação e evolução

Os módulos incluem fixtures e testes offline para duplicidade, revisões, ausência de alertas, indisponibilidade, boletins vencidos, unidades, identificação municipal e publicação sintética.

A disponibilidade das APIs INMET e Aviation Weather Center, e o formato retornado em produção, **precisam ser conferidos no primeiro workflow real após o merge**. Não foram realizadas consultas de rede no ambiente local de desenvolvimento.

### Próximos passos

- Confirmar integração pública e autorizada com pluviômetros reais (INMET, Cemaden, Epagri/Ciram).
- Preservar os detalhes das observações de interesse em um repositório histórico externo e particionado.
- Projetar eventos hidrometeorológicos a partir de séries medidas, com controle de qualidade, sem confundi-los com avisos oficiais.
- Avaliar maior frequência para consultas de avisos quando as quotas e a estabilidade forem verificadas, sem prometer atualização em tempo real.

