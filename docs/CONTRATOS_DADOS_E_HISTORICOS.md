# Contratos de dados, identidade e retenção

**Referência:** código de `main` no commit `3ec7bb9`, consultado em 14/11/2026. Os campos aqui descritos são interfaces de publicação; este documento não é uma especificação JSON Schema completa.

## 1. Fluxo de geração

`scripts/build_site.py` consulta fontes através de `src/observatorio/`, recupera históricos selecionados da publicação anterior, normaliza as evidências, calcula síntese, classificação e artefatos, copia `web/` para uma árvore temporária, executa `scripts/validate_site.py` e substitui o destino local. O workflow `pages.yml` valida o diretório novamente antes de publicar. O browser consome arquivos estáticos por HTTP; não autentica diretamente provedores.

A pasta `data/` abaixo é **saída gerada em `dist/data/`**, não diretório de fonte versionado na `main`. Cada produto JSON recebe `publication_at` no momento da criação. Arquivos de cada município ficam em `data/places/{id}.json`, com IDs provenientes de `config/locations.json`.

## 2. Inventário dos produtos gerados

| Arquivo em `data/` | Finalidade e cautela |
| --- | --- |
| `latest.json` | Manifesto de localidades, estado da coleta do modelo, `generated_at`, marcadores de históricos e estado parcial |
| `places/{id}.json` | Produto municipal normalizado do Open-Meteo; estimativa/previsão, **não medição instrumentada** |
| `dashboard.json` | Apresentação sintética de Araquari; `synthesis` e `risk_classification` consultiva; `assessment` legado permanece distinto |
| `analysis.json` | Contexto e análise consultiva por localidade |
| `coverage.json` | Cobertura declarada por localidade, fonte e variável; disponibilidade não equivale a qualidade perfeita |
| `territorial_alignment.json` | Proximidades exploratórias entre pontos, estações e grade de modelo; não prova equivalência |
| `regional_quality.json` | Contexto regional de qualidade/temporalidade das fontes |
| `forecast_comparison.json` | Comparações de modelos e produto municipal INMET; faixa entre modelos não é probabilidade |
| `inmet_forecast.json` | Previsão municipal diária/por turno, com textos/temperaturas e prazos próprios |
| `model_forecast_history.json` | Rodadas de previsões preservadas para confronto e contingência, não observações |
| `forecast_snapshot.json` | Referência de previsão anterior; não mede o tempo passado |
| `history.json` | Último snapshot de modelo por dia e município, em janela móvel de 366 dias |
| `observation_history.json` | Histórico observado das estações elegíveis de Araquari, até sete dias |
| `multisource_history.json` | Evidências locais normalizadas, amostras de avaliação e histórico consultivo com limites de volume |
| `assessment_history.json` | Episódios de **estados amostrados** e avisos; intervalo entre coletas não é duração ininterrupta do fenômeno |
| `alerts.json` | Avisos INMET associados por código IBGE; distinguir sucesso sem avisos, falha e aviso com janela incerta |
| `notice_history.json` | Arquivo de avisos INMET e presença em consultas; ausência posterior não comprova cancelamento |
| `observations.json` | Boletins METAR de aeródromos; proximidade não equivale a medição municipal |
| `stations.json` | Catálogos INMET de estações: metadados, não telemetria |
| `rain_gauges.json` | Chuva recente INMET, dependente de acesso legítimo e leituras elegíveis |
| `inmet_archive.json` | Arquivo anual INMET com atraso, não medição atual |
| `cemaden.json` | Acumulados recentes de chuva por pluviômetro/município |
| `cemaden_sensors.json` | Sensores regionais Cemaden; unidade e intervalo podem exigir confirmação |
| `campus_station.json` | Dados da estação IFC via API pública, com períodos, limitações de contador e validade |
| `cptec.json` | Previsão CPTEC diária, independente da previsão horária |
| `nasa_power.json` | Estimativas diárias em grade, não leituras de estação |
| `defesa_civil_sc.json` | Publicações e contexto qualitativo; acesso ao portal falhou no runner investigado em 13/11 |
| `epagri_geo.json` | Cadastro geográfico de estações; não telemetria |
| `epagri_notices.json` | Avisos Epagri/Ciram, com requisitos de abrangência/validade |
| `epagri_bulletins.json` | Boletins editoriais Epagri e datas/áreas interpretáveis |

A relação vem das chamadas `publish_json(...)` no final de `scripts/build_site.py`. Não assuma que todo arquivo contém medidas disponíveis em toda coleta.

## 3. Identidade, relógios e integridade

- `latest.json.generated_at` identifica o momento lógico da publicação; o `publication_at` de **todos os JSON da mesma geração** deve coincidir com ele. A verificação rejeita misturas de gerações.
- `collected_at`, `retrieved_at`, `reference_at`, `observed_at`, `issued_at` e `valid_until` têm significados distintos. Não use `publication_at` para renovar automaticamente a validade original de uma consulta antiga.
- A comparação no navegador deve aceitar somente manifestos e produtos da mesma geração, conforme seus contratos, realizando nova tentativa limitada durante propagação CDN.
- Um status `available` significa produto recebido/interpretado conforme o adaptador, não confirmação universal de cobertura, funcionamento da estação ou equivalência territorial.
- `null`, `unavailable`, `stale` e cobertura incompleta **não significam zero meteorológico**. Status de consulta e existência de aviso são dimensões separadas.
- A validação de produção rejeita `fixture_mode`. O exemplo sintético precisa do modo de validação `--fixture`.
- `risk_classification.method_version` atualmente é `araquari-risk-v4`; `official_level` permanece `null`. `synthesis.risk_classification` compartilha a classificação da home. O produto `assessment` anterior serve para auditoria/compatibilidade e não substitui o nível consultivo.
- A avaliação de candidatos usa vencimentos próprios. O navegador pode reavaliar expiração/precedência já publicada, sem buscar novos dados meteorológicos ou transformar o resultado em decisão institucional.

## 4. Retenção e limites implementados

| Histórico | Política observada no código |
| --- | --- |
| `history.json` | `merge_daily_publications(..., keep_days=366)`, no máximo um snapshot de modelo por município/dia; valida até 12.000 registros anteriores |
| `notice_history.json` | `KEEP_DAYS=366`, `MAX_RECORDS=2000` |
| `observation_history.json` | `RETENTION_DAYS=7`, `MAX_HISTORY=6000` |
| `multisource_history.json` | Evidências de até sete dias e 6.000 registros; avaliações limitadas a 336, conforme método multifontes |
| `model_forecast_history.json` | Até 64 publicações arquivadas e tamanho validado de até 5 MB; a disponibilidade histórica não prolonga o prazo de uma previsão recuperada |
| `assessment_history.json` | Até 366 dias, 3.000 episódios e 500 avisos; estados amostrados, não duração comprovada |
| `forecast_snapshot.json` | Estado de comparação anterior, até 49 registros horários por município e tamanho de até 1 MB |

Os limites são barreiras de integridade e custo; não devem ser elevados sem avaliar tamanho final, tempo de download, quotas e efeito sobre o Pages. O arquivo de modelo por dia não permite calcular médias climáticas medidas.

## 5. Recuperação do estado anterior

Em produção, `--previous-url` aponta para o Pages. O build tenta recuperar produtos de histórico com controle de formato/tamanho, repetição limitada em erros transitórios e verificação de marcadores `*_published` em `latest.json`. Quando um histórico obrigatório antes publicado desaparece ou é inválido, a operação **falha fechada**, para evitar publicar um histórico artificialmente esvaziado. Produtos de cache opcionais podem falhar sem exigir apagar o histórico obrigatório.

A publicação remota não é transação simultânea com o histórico de todas as fontes; a geração local é validada e trocada atomicamente, e o deploy é uma etapa posterior. O Pages não constitui backup independente. Não há escrita de dados dinâmicos em commits Git a cada 30 minutos, nem integração atual com Drive ou banco pago.

## 6. Como auditar um nível

1. Registre o `generated_at` de `data/latest.json` e confirme a identidade de `data/dashboard.json`.
2. Leia `risk_classification.method_version`, `level`, `reason`, `basis`, `valid_until` e `official_level`.
3. Examine `candidates[]`, suas evidências e vencimentos, além de `requirements[]` para o caminho de Normalidade.
4. Confira origem, município/estação, janela e unidade no dado bruto correspondente. Informe quando uma fonte é regional, qualitativa, de consulta anterior ou está indisponível.
5. Não apresente a classificação consultiva como despacho oficial, risco universalmente ausente ou autorização automática de atividades.

Detalhamento normativo/metodológico: [classificação v4](CLASSIFICACAO_CONSULTIVA.md) e [aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md).

**Manutenção:** mudanças de contrato exigem atualização coordenada de produtor, validador, consumidor web, testes e documentação. Nunca altere só um JSON de exemplo para “corrigir” a produção.
