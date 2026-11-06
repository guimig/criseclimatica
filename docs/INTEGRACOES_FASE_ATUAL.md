# Integrações, situação da chuva observada e políticas de falha

Este documento registra a rodada de desenvolvimento focada em **fazer as fontes funcionarem**.
Nenhuma política de retenção ou cópia histórica externa foi alterada nesta etapa.

## Diagnóstico: por que a chuva INMET não aparece?

O arquivo `data/rain_gauges.json` é preenchido pelo adaptador em
`src/observatorio/inmet_rain.py`. O catálogo público de estações INMET
**contém metadados, não medições**. Para consultar dados horários o adaptador
usa uma interface distinta, que atualmente depende de uma credencial
`INMET_API_TOKEN`. O contrato de disponibilidade desse endpoint para programas
externos **não está confirmado**, e projetos públicos relatam bloqueios ou
respostas vazias.

Estados publicados:

- `not_configured`: a variável de ambiente `INMET_API_TOKEN` não foi definida;
  não se tentou consultar o serviço autenticado.
- `access_restricted`: requisições foram rejeitadas por controle de acesso
  (HTTP 401/403). Isso não comprova que a credencial esteja incorreta;
  o endpoint também pode impor restrições adicionais.
- `no_recent_data`: as estações consultadas não retornaram leituras recentes;
  isso **não representa chuva zero**.
- `no_nearby_catalog_stations`: o catálogo não ofereceu estações selecionáveis
  dentro da distância definida.
- `unavailable`: erros de comunicação, endpoint ou dados inválidos impedem
  confirmar medições.
- `available`: existe pelo menos uma estação com leitura válida, identificada
  por código e horário. Erros nas outras estações constam em `failure_reasons`.

O segredo deve ser configurado em **Settings → Secrets and variables → Actions →
New repository secret**, nome `INMET_API_TOKEN`, após obter autorização legítima
junto ao INMET. A API pode continuar bloqueada mesmo com um token: nesse caso,
solicitar ao órgão uma modalidade automatizável oficialmente suportada.
**Não** copiar tokens para issues, código, JSON, HTML ou mensagens públicas.

Os dados são **brutos**, podem apresentar `9999`, lacunas e problemas de
sensores. Precipitação acumulada de 24 leituras só aparece com cobertura
integral. O fluxo de publicação não é interrompido se esta fonte falhar.

## Nova integração: Cemaden PED

O Cemaden oferece o serviço oficial `GET
/PED/rest/pcds-acum/acumulados-recentes`, cuja [especificação Swagger](https://sws.cemaden.gov.br/PED/api/ui/)
determina o envio de um **JWT no cabeçalho `token`** e permite filtrar pelo
código IBGE. A resposta contém `acc1hr`, `acc24hr`, `codestacao` e `datahora`.
O código consulta somente os sete municípios cadastrados, com até três
requisições simultâneas, e rejeita observações antigas, futuras, negativas,
malformadas ou atribuídas a outro município.

- Para habilitar: configurar o segredo **`CEMADEN_PED_TOKEN`** no GitHub Actions
  somente depois de obter autorização e um JWT válido por via oficial.
- JWTs expiram: uma credencial estática não garante funcionamento contínuo;
  a renovação automática dependerá do fluxo de autenticação oficialmente
  disponibilizado ao projeto.
- Sem token: o estado será `not_configured`, sem falsas medições.
- Com token válido e estações transmitindo: `available`, com observações
  atribuídas **a cada estação**, e não à chuva média de todo o município.

A API foi implementada conforme o contrato documentado e testada com
respostas simuladas. Nenhuma credencial real foi testada nesta etapa.

## Nova integração: NASA POWER

A [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/)
é pública e não utiliza token nas consultas desenvolvidas. A aplicação consulta
apenas um **ponto de referência em Araquari**, em horário UTC, para reduzir o
tráfego e evitar consultas repetidas ao mesmo grid espacial.

- Produto `PRECTOTCORR`: precipitação **estimada por grade**, não observada
  por pluviômetro.
- Produto `T2M`: temperatura estimada; os dias são identificados em UTC.
- Período: somente um conjunto pequeno de dias recentes; o serviço pode ter
  latência de publicação e informar dados ausentes (`-999`).
- Frequência: no máximo uma nova consulta diária quando um resultado recente
  já foi publicado. O último resultado pode aparecer como `cached` ou `stale`
  por até 72 horas em caso de falha, com horário original preservado.
- Os dados NASA **não substituem** chuva INMET/Cemaden nem os valores de
  previsão Open-Meteo. Não são apresentados como chuva observada em Araquari.

## Transparência e funcionamento

O site publica `data/nasa_power.json` e `data/cemaden.json`, além dos arquivos
já existentes. A seção **Estado das integrações** lista, separadamente:
Open-Meteo, catálogo e avisos INMET, METAR/NOAA, chuva INMET,
chuva Cemaden e NASA POWER. Os estados `not_configured`, `unavailable`,
`access_restricted`, `no_recent_data`, `stale` e `cached` são diferentes.

O script `scripts/build_site.py` imprime um resumo sanitizado dos estados,
sem URLs de credenciais. Falha de fonte secundária **não impede** atualizar
as previsões disponíveis. A validação `scripts/validate_site.py` rejeita
publicações sintéticas e rótulos de origem incorretos.

### Validação operacional após o merge

1. Em **Actions**, executar `Update forecast and publish Pages`.
2. No passo **Fetch live forecast and build static site**, conferir a linha
   `Provider status: ... nasa=... cemaden=... inmet_rain=...`.
3. Consultar `data/nasa_power.json`, `data/cemaden.json` e
   `data/rain_gauges.json` no Pages; conferir `status`, `checked_at`, fonte e
   leituras por estação.
4. Se `nasa=unavailable`, examinar a conectividade/limites do serviço NASA no
   runner e manter transparência na interface. Se `cemaden=not_configured`
   ou `inmet_rain=not_configured`, esse é o comportamento esperado sem token.
5. Conferir a versão publicada em navegador móvel. A validação da primeira
   consulta real aos novos serviços ainda precisa ser confirmada em Actions.

## Próximas fontes a estudar, sem promessas prematuras

- **Epagri/Ciram:** dados regionais relevantes, mas interface pública REST de
  consulta periódica ainda não confirmada; não automatizar o portal sem
  autorização.
- **ANA:** integração hidrológica depende das condições atuais da API e da
  concessão de acesso.
- **CPTEC/INPE:** há serviços XML documentados, mas a publicação/reprodução
  deve respeitar as condições e autorizações do órgão.
- **Cemaden:** priorizar regularização de credenciais e atualização contínua.
- **INMET:** buscar acesso oficialmente suportado a observações horárias.

Nenhuma fonte bloqueada será substituída por valores estimados apresentados
como se fossem observações instrumentais.
