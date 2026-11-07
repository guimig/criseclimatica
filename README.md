# Observatório do Tempo e Clima

Portal meteorológico aberto com prioridade em Araquari e cobertura de vinte municípios de Santa Catarina e Paraná. Python coleta e processa dados no GitHub Actions; GitHub Pages publica HTML, CSS, JavaScript e JSON. Sem banco pago, Google Sheets, backend no navegador ou credenciais públicas.

## Painel de acompanhamento de Araquari

A página inicial reúne nível de referência, aviso prioritário Epagri/Ciram, quatro indicadores e gráfico interativo. Previsão, observações, chuva, vento/rajadas e temperatura podem ser explorados por período, ponteiro, toque e teclado. Fontes, estações e municípios complementares permanecem em `dados.html`, fora da leitura principal.

**PN 13/2026 e PN 14/2026 — ASSINST/REI** substituem o protocolo anterior. As seis categorias são qualitativas; não se atribui um nível por média de chuva/vento ou pela cor de outro órgão. O enquadramento é uma sugestão rastreável, quando há evidência prioritária suficiente; a decisão formal permanece humana. Ausência de dados nunca produz verde automático.

Há distribuição de chuva por estações contemporâneas (mediana com n ≥ 3 e extremos preservados), previsão de até dez dias, revisão dos mesmos horários futuros e histórico observado de sete dias sem reconstrução retroativa. O visual é claro, verde e branco, independente e sem logotipos oficiais. Veja [métodos, critérios, normas e limites](docs/PAINEL_ARAQUARI_PN13_PN14.md).

## Leitura multifontes e memória

O painel usa referências numéricas auxiliares INMET para chuva e vento, com variáveis, janelas e fontes identificadas. Coincidências temporais e geográficas podem subsidiar sugestões consultivas, preservando a prioridade Epagri/Ciram e sem média de cores ou nota única de risco. Estados neutros distinguem **monitoramento de rotina**, **monitoramento parcial** e referências de atenção. O gráfico começa com passado observado e previsão separados; a memória mostra estados registrados e validade dos avisos, sem confundir isso com duração de desastre. Há alternância entre tema claro e escuro. Veja [metodologia, limites e históricos](docs/LEITURA_MULTIFONTES_E_MEMORIA.md).

## O que está implementado

- Open-Meteo: estimativas atuais e previsão horária/diária, com identificação explícita de modelo.
- Avisos INMET por código municipal IBGE e arquivo progressivo de avisos; não são registros de desastres confirmados.
- METAR/NOAA: consulta conjunta de Joinville (SBJV), Navegantes (SBNF), Blumenau (SSBL), Florianópolis (SBFL), Afonso Pena (SBCT) e Bacacheri (SBBI). Exibe todos os boletins válidos até 180 km, distinguindo contexto regional acima de 100 km e mantendo a observação principal dentro de 100 km.
- Cemaden PED: acumulados de 1–120h por estação e consulta regional SC/PR de sensores recentes, com SGAA e limite compartilhado de requisições. Sensores: até 24 estações por localidade em um raio de 130 km; acumulados municipais: todas as estações retornadas, sem o antigo corte de seis na interface.
- INMET: catálogos automático/convencional, arquivo anual observado com atraso e adaptador de precipitação recente condicionado a acesso autorizado.
- Epagri: cadastro de estações, avisos meteorológicos e boletins editoriais; cadastro não é telemetria.
- CPTEC: previsão independente para a localidade de referência; NASA POWER: estimativas diárias em grade para Araquari.
- Defesa Civil SC: coletor experimental de publicações, com indisponibilidade explícita quando os canais não respondem.
- Cobertura por localidade, fonte, variável e horário em `data/coverage.json` e na interface.

A cobertura usa vinte pontos municipais, em quatro núcleos: Norte de SC, Vale e foz do Itajaí, Grande Florianópolis e Curitiba/planalto. Os dez pontos originais são preservados; entram Navegantes, Penha, Balneário Piçarras, Guaramirim, Gaspar, Pomerode, Florianópolis, São José (SC), Curitiba e São José dos Pinhais. Os pontos são aproximações de amostragem selecionadas para o projeto, não centroides oficiais nem polígonos municipais. Núcleos são agrupamentos operacionais, não regiões climaticamente homogêneas.

`data/territorial_alignment.json` e o painel de áreas comuns indicam proximidade entre modelo e estações, distância entre as estações, diferença temporal, referência da grade devolvida pelo Open-Meteo e variáveis potencialmente comuns. O raio exploratório é 25 km, com prioridade geométrica a 10 km; são parâmetros de triagem, não padrões de equivalência meteorológica. Altitude, relevo e protocolos ainda precisam de verificação. Não se calcula precisão, viés ou erro de previsão. Veja [áreas comuns](docs/ALINHAMENTO_TERRITORIAL.md).

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

A ampliação das redes está descrita em [Estações Cemaden e METAR](docs/AMPLIACAO_ESTACOES.md). Seleção geográfica não garante disponibilidade de boletim ou representatividade local.
