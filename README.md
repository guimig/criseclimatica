# Observatório do Tempo e Clima

Portal meteorológico aberto com prioridade em Araquari e cobertura de dez municípios de Santa Catarina. Python coleta e processa dados no GitHub Actions; GitHub Pages publica HTML, CSS, JavaScript e JSON. Sem banco pago, Google Sheets, backend no navegador ou credenciais públicas.

## O que está implementado

- Open-Meteo: estimativas atuais e previsão horária/diária, com identificação explícita de modelo.
- Avisos INMET por código municipal IBGE e arquivo progressivo de avisos; não são registros de desastres confirmados.
- METAR/NOAA: observações nos aeródromos de Joinville e Navegantes, sem atribuição a todo o município.
- Cemaden PED: acumulados de 1–120h por estação e consulta regional de sensores recentes, com SGAA e limite compartilhado de requisições.
- INMET: catálogos automático/convencional, arquivo anual observado com atraso e adaptador de precipitação recente condicionado a acesso autorizado.
- Epagri: cadastro de estações, avisos meteorológicos e boletins editoriais; cadastro não é telemetria.
- CPTEC: previsão independente para a localidade de referência; NASA POWER: estimativas diárias em grade para Araquari.
- Defesa Civil SC: coletor experimental de publicações, com indisponibilidade explícita quando os canais não respondem.
- Cobertura por localidade, fonte, variável e horário em `data/coverage.json` e na interface.

Os pontos de amostragem são Araquari, Joinville, São Francisco do Sul, Itapoá, Garuva, Balneário Barra do Sul, Barra Velha, Blumenau, Itajaí e Jaraguá do Sul. Coordenadas aproximadas não representam polígonos municipais nem estações.

## Confiabilidade e limites

A chuva prevista na janela de 24h só tem total quando os 24 intervalos horários estão presentes e válidos. Duplicações idênticas são consolidadas; conflitos invalidam o intervalo. Como a precipitação horária Open-Meteo refere-se à hora anterior, a janela começa na hora UTC corrente e termina 24 horas depois, incluindo a hora em curso. A interface informa início, fim, cobertura e soma parcial separada. Referência: [definições horárias Open-Meteo](https://open-meteo.com/en/docs).

Cemaden distingue falha de consulta municipal de consulta sem leitura válida. Ausência de dado nunca equivale a 0 mm. O navegador reavalia a idade dos dados a cada minuto e ao retornar à página, sem consultar diretamente APIs autenticadas. Leituras instrumentais vencidas deixam de aparecer como atuais; horários permanecem visíveis nos resumos de cobertura.

Se todas as previsões Open-Meteo falharem, outras fontes operacionais ainda podem ser publicadas com estado parcial e os cartões do modelo vazios. Se nenhuma fonte operacional puder ser atualizada, o build aborta e preserva a publicação anterior. Catálogos e arquivo anual, isoladamente, não justificam publicar um painel aparentemente atualizado.

O agendamento é de três horas, sujeito a atrasos do Actions. Não é monitoramento de emergência em tempo real. Consulte diretamente as autoridades em situações de risco.

## Estrutura e execução

- `src/observatorio/`: adaptadores, normalização, qualidade, cobertura e arquivos compactos.
- `scripts/build_site.py`: coleta, recuperação do estado anterior e geração atômica do site.
- `scripts/validate_site.py`: valida os contratos antes da publicação.
- `web/`: interface responsiva sem dependências de frontend.
- `tests/`: cenários Python e comportamento JavaScript com DOM simulado.
- `.github/workflows/`: CI e publicação agendada/manual.

Requer Python 3.11+ e Node.js para as verificações JavaScript; sem instalação de bibliotecas externas.

```bash
python -m unittest discover -s tests -v
python -m compileall -q src scripts
node --check web/app.js
node tests/web_reliability.cjs
python scripts/build_site.py --output dist
python scripts/validate_site.py --output dist
python -m http.server 8000 --directory dist
```

Para build de teste sem consultar provedores:

```bash
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --output dist
python scripts/validate_site.py --output dist --fixture
```

Dados sintéticos são recusados pela validação de produção e pelo navegador. O teste JavaScript usa um DOM simulado; não substitui inspeção visual em celular e desktop.

## Publicação e credenciais

Em **Settings > Pages**, usar **GitHub Actions**. O workflow `Update forecast and publish Pages` publica em [guimig.github.io/criseclimatica](https://guimig.github.io/criseclimatica/). O botão do site recarrega os arquivos já publicados; não dispara coleta no Actions.

Credenciais opcionais ficam exclusivamente em Repository secrets, no passo Python:

- `CEMADEN_PED_EMAIL` e `CEMADEN_PED_PASSWORD`: autenticação SGAA; `CEMADEN_PED_TOKEN` é compatibilidade legada.
- `INMET_API_TOKEN`: somente quando houver acesso legítimo confirmado ao serviço de observações recentes.

Não incluir credenciais em código, logs, issues ou navegador. Configurar um segredo não comprova cobertura ou disponibilidade de uma API. Veja [autenticação Cemaden](docs/CEMADEN_PED_AUTENTICACAO.md).

## Histórico e continuidade

O Pages recupera da publicação anterior um snapshot diário de modelo por localidade e um arquivo de avisos, limitados a 366 dias. Snapshot não é média diária, precipitação medida nem série climatológica. Esses arquivos não são backup independente. Falhas de leitura abortam a publicação quando houver risco de perda; o desaparecimento de histórico marcado como publicado também é rejeitado.

Sem commits de dados a cada ciclo, Drive ou armazenamento histórico externo nesta etapa. A decisão vigente é amadurecer integrações antes de ampliar persistência. Há utilitários JSONL.GZ locais para evolução futura.

Consulte [roadmap atual](docs/ROADMAP.md), [decisões](docs/DECISOES.md), [arquitetura](docs/ARQUITETURA.md), [fontes](docs/FONTES.md) e [pacote de confiabilidade](docs/CONFIABILIDADE.md). Os documentos das etapas anteriores preservam os diagnósticos da época; o roadmap concentra o estado atual.
