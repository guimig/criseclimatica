# Correções de integração e novas fontes regionais — etapa 8

## Diagnóstico comprovado no código

O catálogo INMET persistido de versões anteriores não garantia o campo `network_type`. A função antiga `nearby_station_codes` exigia literalmente `network_type == automatica` e descartava registros automáticos Axxx sem esse atributo. Isso explica um **caminho concreto** para `inmet_archive=no_nearby_stations` mesmo com o ZIP oficial acessível. A falha não exige, por si, que as estações estejam inativas.

## Correção do INMET

- Reconhecer códigos `A` e 3–4 dígitos de catálogos legados quando não houver `network_type`, sem aceitar registros declarados como convencionais.
- Ler metadados **somente dos primeiros 4096 bytes** dos membros CSV do ZIP anual oficial (código WMO, nome, latitude, longitude); conferir correspondência código do cabeçalho ↔ código do nome do arquivo.
- Usar essas informações para selecionar estações dentro de 130 km das localidades mesmo quando o catálogo remoto não fornece registros. Não extrair arquivos para disco e manter limites de tamanho/quantidade.
- Preservar a política de chuva medida: dias com 24 leituras válidas são elegíveis para total diário; horas ausentes aparecem como cobertura parcial. Nenhum valor é mostrado como precipitação atual.
- Não reaproveitar indefinidamente o estado antigo `no_nearby_stations` produzido antes da nova descoberta do arquivo (`station_discovery_version=2`).

## Epagri — cadastro geográfico

Serviço oficial de camada ArcGIS: https://gis.epagri.sc.gov.br/arcgis/rest/services/Zoneamento/Potencial_estacoes/MapServer/1

A camada possui atributos como nome, município, coordenadas, categoria e situação cadastral. A consulta REST usa um envelope delimitado ao norte de SC e `inSR=4326`, retorna apenas atributos e valida quantidade e integridade antes de computar distâncias geodésicas. O arquivo público `data/epagri_geo.json` contém no máximo seis estações por município, e não contém medições.

**Restrição:** a denominação da camada (“Estações ativas atuais”) não comprova manutenção operacional recente. Ela é um catálogo de localização, não uma API de leitura instrumental.

## Epagri/Ciram — avisos meteorológicos oficiais

Fonte: https://ciram.epagri.sc.gov.br/index.php/category/avisos-meteorologicos/feed/

A consulta obtém publicações RSS com links HTTPS do domínio institucional. Usa a data de publicação da fonte; extrai “Início”, “Fim” e “Regiões” apenas quando expressamente presentes no texto completo do RSS. Um aviso que menciona “Litoral Norte” ou “todas as regiões” **não** é rotulado automaticamente como alerta municipal ou da Defesa Civil. A interface sempre encaminha à publicação oficial para detalhes.

Cache opcional do estado publicado por até três horas, com rótulo `cached`; em falhas, apenas até 48 horas como `stale`. Esta opção não altera o armazenamento histórico acordado.

## Defesa Civil SC

A coleta automatizada do domínio estadual ainda não foi comprovada. O workflow `42153693634` registrou `URLError` para WordPress, RSS e listagem institucional. Os avisos da Epagri são **uma fonte complementar separada**, não um substituto oculto que passa a se chamar “Defesa Civil”. A indisponibilidade oficial permanece transparente no painel.

## Testes e implantação

1. `python -m unittest discover -s tests -q`
2. `python -m compileall -q src scripts`
3. `node --check web/app.js`
4. `python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --output dist`
5. `python scripts/validate_site.py --output dist --fixture`
6. Após CI verde, merge e revisão de `Update forecast and publish Pages`: conferir as palavras `inmet_archive`, `epagri_geo`, `epagri_notices`, mais o probe de conectividade no CI do PR.

Não acessar endpoints privados, não contornar CAPTCHA e não publicar credenciais. Sem API confiável da Defesa Civil ou nova pluviometria recente, a interface continua a expor explicitamente suas limitações.
