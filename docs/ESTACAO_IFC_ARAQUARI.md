# Estação meteorológica do IFC Araquari

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


Integração implantada em 09/11/2026 para acompanhamento local. **Participa da síntese meteorológica local com peso igual às demais estações nas variáveis compatíveis; não define nível institucional. Contador diário não é equiparado ao acumulado móvel de 24 h.** A instalação, calibração e metodologia dos sensores ainda precisam de confirmação com os responsáveis pela estação.

## Acesso e coleta

- [Painel público da estação](https://mytb.fabricadesoftware.ifc.edu.br/dashboard/6c46c4f0-5613-11f0-ac33-dfcfe81f8a64?publicId=f2146870-34a4-11f0-ac33-dfcfe81f8a64), hospedado no ThingsBoard da Fábrica de Software do IFC.
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
