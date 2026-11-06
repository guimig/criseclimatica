# Ampliação das estações — 06/11/2026

## Cemaden

A consulta de sensores já recupera dados recentes de toda Santa Catarina em uma única requisição regional. A seleção geográfica passa de seis estações em 85 km para até 24 em 130 km por localidade. `eligible_station_count` informa quantas estações válidas existem no raio antes do limite; `selection` publica os parâmetros usados. Coordenadas, cidade de origem, unidade confirmada e idade de cada leitura continuam preservadas. Não é cobertura municipal nem seleção hidrológica por bacia.

Os acumulados por IBGE já consultam todas as estações dos dez municípios configurados, sem filtro de código de estação. Mantém-se esse acesso e o teto de segurança de 300 registros por resposta. Foi removido o corte visual em seis pluviômetros: os demais ficam em detalhes expansíveis. Não se apresenta observação de outra cidade como acumulado municipal. O diagnóstico por município e o limitador compartilhado de nove requisições por 61 segundos continuam ativos; esta mudança não aumenta as chamadas Cemaden.

## NOAA / METAR

Uma requisição consulta SBJV, SBNF, SSBL, SBFL, SBCT e SBBI. Somente boletins efetivamente retornados, com coordenadas e idade válidas, são publicados. `queried_stations` distingue código consultado de boletim disponível. `locations[].stations` relaciona todos os aeródromos válidos até 180 km, ordenados por distância. `scope=regional_context_only` identifica referências acima de 100 km.

Os campos legados `observation` e `distance_km` continuam restritos ao aeródromo válido mais próximo dentro de 100 km. Uma estação entre 100 e 180 km não preenche a observação principal. No painel ela aparece com aviso expresso de contexto regional. Não são calculadas médias entre aeródromos ou totais fictícios de chuva. Há distinção entre fonte indisponível, código sem boletim recente e estação distante.

## Apresentação e validação

Cemaden mostra seis cartões inicialmente e oferece os restantes em seção expansível; o conjunto publicado não sofre o antigo corte visual. METAR mostra todas as referências locais elegíveis. O resumo de cobertura conta todos os boletins associados e indica quantos são apenas regionais. A idade das medições é reavaliada pelo navegador como antes.

Os testes cobrem seleção de 24 entre 30 estações, inclusão além do raio antigo e exclusão fora do novo, coleta de todos os pluviômetros municipais, consulta única de seis ICAOs, ausência/expiração de boletins, preservação da observação principal e acesso aos cartões adicionais. O validador verifica referências, limites e distâncias. Os logs de publicação informam contagens reais e códigos METAR disponíveis; uma contagem consultada não comprova transmissão contínua.

Fontes primárias: [PED Swagger](https://sws.cemaden.gov.br/PED/api/ui/swagger.json), [AWC Data API](https://aviationweather.gov/data/api/) e [AISWEB/DECEA](https://aisweb.decea.mil.br/). Exemplos oficiais: [Blumenau](https://aisweb.decea.mil.br/?codigo=SSBL&i=aerodromos), [Afonso Pena](https://aisweb.decea.mil.br/?codigo=SBCT&i=aerodromos), [Florianópolis](https://aisweb.decea.mil.br/?codigo=SBFL&i=aerodromos), [Bacacheri](https://ais.decea.mil.br/?codigo=SBBI&i=aerodromos).

Sem novos serviços, credenciais, persistência externa ou mudança no agendamento. Reversão: revert do PR e republicação pelo workflow existente, sem apagar históricos.
