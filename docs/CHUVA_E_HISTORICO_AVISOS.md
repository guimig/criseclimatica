# Chuva instrumental INMET e arquivo progressivo de avisos

## Estado e origem dos dados

Esta etapa introduz `data/rain_gauges.json` e `data/notice_history.json`, ambos gerados pelo workflow Python. O primeiro **só terá leituras medidas se houver autorização para a API do INMET e respostas válidas**; o segundo armazena um catálogo compacto de **avisos oficialmente emitidos**, não desastres confirmados.

### 1. Estações pluviométricas INMET (opcional)

- **Fonte:** INMET, estações automáticas; uso de séries horárias brutas e não validadas pelo órgão. A [orientação do INMET](https://portal.inmet.gov.br/noticias/saiba-como-acessar-os-dados-meteorol%C3%B3gicos-dispon%C3%ADveis-no-site-do-inmet) menciona valores ausentes `9999`, `Null` e dados brutos sem validação.
- **Acesso:** módulo experimental que consulta o endpoint de observações que requer token (`/token/estacao/INICIO/FIM/CODIGO/TOKEN`), descrito em implementações públicas de terceiros. Sua disponibilidade efetiva **ainda precisa ser validada** pelo mantenedor com credencial própria e autorização apropriada. Não são feitas consultas anônimas tentando contornar bloqueios.
- **Como habilitar:** obter um token legítimo diretamente com o INMET. Em `guimig/criseclimatica` acessar **Settings → Secrets and variables → Actions → New repository secret** e criar `INMET_API_TOKEN`. Nunca colocar o token em arquivos, URLs públicas, issues, logs ou no chat.
- **Sem token:** o workflow continua normalmente, publica `status: not_configured` e o painel não inventa valores observados.
- **Seleção das estações:** até cinco estações automáticas próximas de pontos regionais, dentro de 90 km, conforme o catálogo INMET disponível. A distância geográfica **não comprova representatividade municipal**. A API consulta apenas as estações selecionadas, a cada ciclo de publicação (atualmente três horas), e não todas as estações do Brasil.
- **Qualidade:** valores não numéricos, negativos, fora de escala ou marcadores de ausência viram `null`, nunca zero. Leituras horárias conflitantes não são consolidadas; dados com mais de seis horas são descartados como observação recente.
- **Precipitação acumulada:** somente se existirem 24 leituras horárias consecutivas, sem dados ausentes, o campo `rain_last_24_readings_mm` será apresentado. Se a cobertura for incompleta, o campo será `null` e a interface mostrará a quantidade de leituras disponíveis. Não equivale necessariamente às últimas 24 horas exatas a partir do momento da consulta.
- **Segurança:** o token é enviado somente no processo do GitHub Actions e não é publicado no Pages. O cliente desabilita redirecionamentos da requisição autenticada, limita tamanho/tempo e evita registrar a URL que contém a credencial.

Estados do dataset: `not_configured`, `no_nearby_catalog_stations`, `available`, `unavailable` e `fixture_mode` (apenas para testes que nunca podem ser publicados).

### 2. Arquivo progressivo de avisos do INMET

`data/notice_history.json` mantém registros oficiais que apareceram nos avisos municipais do INMET: tipo, gravidade, período **exatamente como informado pela fonte**, municípios por código, revisão, primeira e última observação no feed. O mesmo aviso em dois municípios é guardado uma só vez.

- Um aviso **ausente** em uma consulta válida é marcado como `present_in_latest_successful_feed: false`, e não como cancelado ou encerrado.
- Uma **falha** na fonte não modifica a presença anteriormente conhecida; o painel explica que a situação não pôde ser confirmada.
- O arquivo é recuperado da publicação anterior do GitHub Pages; primeira publicação sem arquivo inicia vazio; erros diferentes de HTTP 404 interrompem a atualização, para evitar descarte silencioso.
- A retenção preliminar é de 366 dias, com limite de 2.000 avisos. Não se pretende gerar commits de histórico a cada atualização.
- A detecção de **avisos emitidos** não comprova tempestade ocorrida, inundação ou dano. Acompanhamento de eventos medidos é um módulo distinto, futuro.

### 3. Limitações importantes

O GitHub Pages **não é um arquivo histórico independente**. Se os arquivos publicados forem perdidos ou substituídos, o histórico progressivo poderá desaparecer. O futuro backend de arquivos JSONL.GZ com armazenamento externo (Drive ou outra alternativa gratuita autorizada) continua prioritário.

As duas fontes devem ser avaliadas nos logs do primeiro workflow real após o merge. Não foram testadas credenciais de produção nem extração horária autorizada neste ambiente. Na ausência delas, `not_configured` é comportamento esperado, não erro do site.

A aplicação continua sendo informativa. Para segurança pública e emergências, consultar Defesa Civil e os portais oficiais.
