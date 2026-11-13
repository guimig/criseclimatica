# Observatório do Tempo e Clima

Portal meteorológico aberto com prioridade em Araquari e cobertura de vinte municípios de Santa Catarina e Paraná. Python coleta e processa dados no GitHub Actions; GitHub Pages publica HTML, CSS, JavaScript e JSON. Sem banco pago, Google Sheets, backend no navegador ou credenciais públicas.

## Inicial e classificação atual

A inicial apresenta o nível consultivo, três comparações entre observado e previsto e dois gráficos interativos. O botão **Entenda a classificação de riscos** explica o nível atual na própria inicial. Avisos positivos Epagri/Ciram e INMET aparecem em blocos recolhidos, com abrangência, período, resumo e link para o anúncio completo. Fontes, estações e métodos ficam em **Dados e fontes**. O nível usa as seis categorias da norma; Normalidade exige cobertura atual e ausência de sinais de atenção. Veja [critérios completos, dados usados e limitações](docs/CLASSIFICACAO_CONSULTIVA.md).

## Interpretação multifontes

O método consultivo v4 amplia o aproveitamento de modelos, previsão municipal INMET/CPTEC, chuva antecedente, METAR e publicações verificáveis. A home permanece concisa; comparações e limitações ficam nos detalhes. Veja [o papel de cada fonte e os critérios de contingência](docs/APROVEITAMENTO_DAS_FONTES.md).

A síntese local usa as quatro estações de Araquari com pesos iguais nas variáveis comparáveis. INMET participa da previsão diária/por turno da inicial; previsões horárias podem ser substituídas por variável quando houver outro produto completo, inclusive de coleta anterior dentro da validade original. A previsão INMET diária/por turno também participa da classificação consultiva, com requisitos próprios de cobertura e medições, sem conversões numéricas de textos. Epagri/Ciram e INMET têm igual relevância meteorológica; a correspondência normativa continua separada da situação meteorológica. Unidades inferidas são identificadas com evidências e limitações. Veja [método atual, cobertura, unidades e critérios](docs/INTERPRETACAO_MULTIFONTES.md).

## Painel de acompanhamento de Araquari

A página inicial **Tempo em Araquari** adota o Painel essencial: nível consultivo, três comparações entre observado e previsto e dois gráficos sempre visíveis, separados entre observações e previsão, com seletor de período direto na tela. Avisos positivos podem ser expandidos na inicial; comparação de modelos e históricos permanecem na página detalhada. No computador, chuva, rajadas e temperatura têm cartões separados; no celular continuam empilhados. A escolha entre **Por estação** e **Ao longo do tempo** fica visível junto aos controles de chuva, com **Área e estação** em filtro separado. Os eixos temporais indicam a unidade; vento e rajada da mesma estação contam como uma única estação na cobertura. Previsão, observações, chuva, vento/rajadas e temperatura podem ser explorados por período, ponteiro, toque e teclado. Fontes, estações e municípios complementares permanecem em `dados.html`, fora da leitura principal.

**PN 13/2026 e PN 14/2026 — ASSINST/REI** substituem o protocolo anterior. As seis categorias são qualitativas; não se atribui um nível por média de chuva/vento ou pela cor de outro órgão. A sugestão é rastreável e combina evidência qualitativa Epagri com apoio quantitativo identificado; o apoio pode elevar a sugestão conforme regras explícitas. A decisão formal permanece humana. Dados ausentes não são tratados como zero; o verde descritivo exige as condições de completude documentadas.

Há distribuição de chuva por estações contemporâneas (mediana com n ≥ 3 e extremos preservados), previsão de até dez dias, revisão dos mesmos horários futuros e histórico observado de sete dias sem reconstrução retroativa. O visual é claro, verde e branco, com tema escuro opcional, independente e sem logotipos oficiais. Veja [layout, interações e compatibilidade do Painel essencial](docs/PAINEL_ESSENCIAL.md). Veja [métodos, critérios, normas e limites](docs/PAINEL_ARAQUARI_PN13_PN14.md).

## Algoritmo dos níveis: documentação completa

Veja [todo o algoritmo da referência dos níveis da norma](docs/ALGORITMO_CLASSIFICACAO_NIVEIS.md): entradas e fontes, municípios e estações elegíveis, janelas temporais, limites de chuva/vento, expressões qualitativas, coincidências, prioridade de integração, completude, validade e cor efetivamente exibida. Inclui inventário datado das estações de Araquari, exemplos e caminhos JSON para auditar cada classificação.

A cor da home, o nível consultivo sugerido e o nível formal são coisas distintas. Amarelo pode representar referência técnica sem nível sugerido; verde é descrição de rotina nos dados acompanhados; o caminho numérico não gera vermelho ou roxo automaticamente. O documento registra também as limitações concretas da flag de completude.

## Leitura multifontes e memória

O painel usa referências numéricas auxiliares INMET para chuva e vento, com variáveis, janelas e fontes identificadas. Coincidências temporais e geográficas podem subsidiar sugestões consultivas, preservando a prioridade Epagri/Ciram e sem média de cores ou nota única de risco. Os estados internos distinguem **monitoramento de rotina**, **monitoramento parcial** e referências de atenção; a apresentação aplica os critérios de cor descritos na documentação do algoritmo. O gráfico começa com observações e previsão separadas; a memória mostra estados registrados e validade dos avisos, sem confundir isso com duração de desastre. Há alternância entre tema claro e escuro. Veja [metodologia, limites e históricos](docs/LEITURA_MULTIFONTES_E_MEMORIA.md).

A apresentação distingue normalidade nos dados monitorados de leitura incompleta, usa as seis cores da norma e permite explorar o entorno sem misturar seus dados com Araquari. Veja [UX, cores e cobertura das estações](docs/UX_E_CORES_DO_PAINEL.md).

## Comparação de previsões

A inicial mostra faixas de 24 h; a área detalhada compara seleção automática Open-Meteo, ECMWF IFS e NOAA GFS por variável e período. CPTEC aparece como contexto diário separado. Não há média, probabilidade ou superioridade local presumida. Previsões futuras são arquivadas por coleta durante sete dias. Veja [fontes, períodos e limites](docs/COMPARACAO_DE_PREVISOES.md).

## O que está implementado

- Open-Meteo: estimativas atuais e previsão horária/diária, com identificação explícita de modelo.
- Avisos INMET por código municipal IBGE, detalhados na home para Araquari e entorno monitorado até 40 km, com arquivo progressivo. Participam da síntese meteorológica com relevância igual à Epagri/Ciram, sem conversão automática em nível institucional nem comprovação de desastre ocorrido.
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

O **cron-job.org** aciona o workflow a cada 30 minutos, 24 horas por dia, nos minutos **00 e 30**, por requisição autenticada `workflow_dispatch`. Esses disparos sempre iniciam coleta. O agendamento GitHub aos minutos 7 e 37 fica como **reserva**: só coleta se a publicação estiver vencida, inválida, inacessível ou com pelo menos 25 minutos. Isso evita coletas duplicadas quando o disparo externo funciona. O navegador verifica versões novas a cada minuto com a aba visível. A publicação depende de concluir coleta, validação e deploy. Veja [configuração e validação do agendamento externo](docs/ATUALIZACOES_30_MINUTOS.md).

## Estrutura e execução

A [auditoria geral de consistência e recuperação](docs/AUDITORIA_GERAL_2026_11_08.md) documenta a identidade compartilhada dos JSON, a recusa de arquivos de publicações diferentes e a recuperação automática do histórico observado.

A [revisão geral da aplicação de 08/11/2026](docs/REVISAO_APLICACAO_2026_11_08.md) registra as correções de backend, frontend, publicação e documentação, com testes e limitações. A [arquitetura](docs/ARQUITETURA.md) descreve o fluxo atual e as garantias de consistência.

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

A página de dados organiza as consultas por assunto, preservando os links diretos e os acumulados completos. Veja [controles, cores e exploração detalhada](docs/EXPLORACAO_DADOS_E_CONTROLES.md).

### Estação no IFC Araquari

A inicial e Dados e fontes → Medições incluem observações da estação do campus, coletadas na API pública do ThingsBoard no ciclo de 30 minutos. Os dados permanecem separados das previsões e da classificação de risco. [Método, unidades, validade e limitações](docs/ESTACAO_IFC_ARAQUARI.md).

### Previsão municipal do INMET

A comparação de fontes inclui o produto municipal do INMET para Araquari, com dias/turnos, temperaturas e textos originais. A comparação usa o mesmo dia civil de Brasília, sem média entre fontes. A classificação consultiva interpreta separadamente os textos por período, conforme os [critérios v4](docs/CLASSIFICACAO_CONSULTIVA.md). Avisos JSON têm uma nova tentativa limitada e preservação identificada de avisos anteriores ainda válidos. [Método e recuperação](docs/INMET_PREVISAO_E_RECUPERACAO.md).

### Defesa Civil SC: textos e disponibilidade

A coleta foi ajustada para a latência observada do portal, passa a obter textos completos e reconhecer títulos atuais, com fallback para `/alerta/`. Alertas encerrados permanecem separados de evidências atuais. Veja [diagnóstico, correções e limites](docs/DEFESA_CIVIL_COLETA_QUALITATIVA.md).
