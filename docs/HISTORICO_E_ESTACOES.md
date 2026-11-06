# Histórico de publicações e catálogo de estações — fase incremental

## O que foi implementado

1. `data/history.json`: um **snapshot de modelo por localidade e por dia civil de São Paulo** (`America/Sao_Paulo`), escolhendo a última coleta válida. Retém os 366 dias mais recentes. Guardamos apenas temperatura instantânea estimada, vento, rajada e a estimativa de chuva para as próximas 24 horas do momento da coleta.
2. `data/stations.json`: as até seis estações automáticas cadastradas mais próximas de cada ponto, selecionadas por distância geodésica em até 170 km. Dados obtidos de `https://apitempo.inmet.gov.br/estacoes/T`; campo de situação é o **estado descrito no catálogo**, e não comprovação de transmissão atual. Não há medidas de sensores INMET integradas.
3. Dois blocos novos no frontend: “Estações próximas” e “Evolução das estimativas”, com identificação das fontes e limitações.

## Recuperação do histórico sem banco pago

Os runners do GitHub Actions são efêmeros. Para não gravar snapshots em cada commit, a tarefa `pages.yml` obtém **o histórico JSON da publicação anterior no próprio GitHub Pages**, adiciona a última coleta do dia e publica a nova versão. Na primeira publicação, `data/history.json` ainda não existe e HTTP 404 indica inicialização.

- Caso a leitura do histórico já publicado falhe por **problema de rede ou erro HTTP diferente de 404**, o build é interrompido antes de substituir o site — prevenção contra perda silenciosa de histórico.
- Um HTTP 404 do arquivo ainda é aceito como início de histórico. Em situações de troca de domínio ou exclusão do arquivo, isso pode reiniciar a série: é necessário backup independente.
- Este mecanismo é **provisório**: histórico embutido no Pages não é backup independente, nem garantia de persistência permanente. O arquivo deve ser copiado periodicamente para repositório separado, Drive ou outro armazenamento externo quando a autenticação estiver configurada.
- São guardados **snapshots publicados de modelo**, não observações instrumentais, médias diárias, valores máximos diários ou acumulados de chuva medida. Logo, não devem fundamentar análises climatológicas.
- As coletas só integram o histórico após o build de pelo menos uma localidade; falha total conserva a publicação anterior. O histórico por localidade é idempotente e mantém a coleta mais recente de cada dia.

## Catálogo INMET

A API de cadastro é consultada no máximo uma vez por 24 horas, aproveitando o JSON anterior quando disponível. Erros são isolados da previsão. A última resposta pode ser exibida por no máximo 7 dias, **identificada como desatualizada**. Em ausência de metadados confiáveis, o painel informa indisponibilidade, sem inventar uma estação.

Os testes offline usam `tests/fixtures/inmet_catalog.json`, criado com valores **fictícios**. Não é publicado como dado real; o portal recusa manifests com `fixture_mode`.

## Próximo ciclo

- Persistência externa real de séries observadas (`JSONL.GZ`) no Drive com OAuth do próprio usuário, sem credenciais expostas no site; validar limites e renovação de tokens.
- Contrato de observações instrumentais do INMET/EPAGRI/Cemaden, quando habilitados e autorizados.
- Retenção por tipo de variável, contagem de observações válidas, detecção de eventos com limiares técnicos e trilha de auditoria.
- Backups independentes dos JSONs do Pages para permitir recuperação em descontinuidade da publicação.

## Execução local e validação

```sh
python -m unittest discover -s tests -v
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --stations-fixture tests/fixtures/inmet_catalog.json --output dist
python scripts/validate_site.py --output dist --fixture
```

A publicação real em `pages.yml` passa `--previous-url https://guimig.github.io/criseclimatica/`, sem credenciais. A consulta real às APIs depende dos ambientes do GitHub Actions e da disponibilidade de cada órgão.
