# Algoritmo de classificação dos níveis — documentação de entrada

**Estado de referência: 14/11/2026.** O código vigente é `src/observatorio/risk_classification.py`, método `araquari-risk-v4`, acompanhado pelo produtor `scripts/build_site.py`, pela síntese `src/observatorio/multisource.py` e pelo validador `scripts/validate_site.py`.

A especificação detalhada está em [Classificação consultiva e inicial objetiva](CLASSIFICACAO_CONSULTIVA.md), complementada por [Aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md) e [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md). **A documentação anterior que citava o método v2 estava desatualizada.**

## Fluxo auditável

1. `build_site.py` obtém dados, fontes complementares e histórico anterior elegível, calcula a síntese e chama `classify(dashboard, selected_detail, stamp)`.
2. O classificador produz candidatos com `level`, `reason`, `basis`, `valid_until` e `evidence`. O candidato de maior gravidade **ainda válido** sustenta o nível. Referências numéricas não são limites definidos nas portarias.
3. `verde` exige cobertura positiva de observações de chuva, previsão quantitativa/qualitativa elegível e consulta de avisos; a mera ausência de alerta não prova Normalidade. Evidência positiva pode sustentar Atenção mesmo com cobertura parcial.
4. Avisos INMET e Epagri/Ciram, medições e modelos numéricos, previsão municipal INMET/CPTEC, boletins editoriais, referências METAR e chuva antecedente possuem regras próprias de elegibilidade e prazo. Candidatos severos exigem critérios adicionais; o sistema **não atribui Calamidade automaticamente**.
5. `data/dashboard.json → risk_classification` publica o resultado; `synthesis.risk_classification` o replica. `assessment` é um produto anterior preservado por compatibilidade. `official_level` permanece nulo: **a autoridade competente decide formalmente**.
6. O navegador, em `web/weather-synthesis.js`, apenas reavalia expiração e precedência dos candidatos publicados, sem buscar novas evidências ou inferir ato oficial.

Os caminhos JSON, identidade dos artefatos e procedimentos de verificação estão em [Contratos de dados e históricos](CONTRATOS_DADOS_E_HISTORICOS.md). Para rastrear uma classificação, guarde a versão e a hora da publicação, as evidências e os vencimentos — não apenas a cor visível.

## Seis categorias e estado sem classificação

As seis categorias da referência institucional são **Normalidade, Preparação, Atenção, Alerta, Alerta máximo e Calamidade**. **Sem classificação** é ausência de evidência suficiente, **não** sétima categoria. O produto `risk_classification` pode estar expirado mesmo que alguns dados observados permaneçam disponíveis. A validade não é renovada pela interface.

## Fontes de verdade

- [Classificação consultiva v4, critérios e limites](CLASSIFICACAO_CONSULTIVA.md).
- [Aproveitamento multifontes, critérios adicionais e contingências](APROVEITAMENTO_DAS_FONTES.md).
- [PN 13/14/2026, papéis institucionais e questões pendentes](PAINEL_ARAQUARI_PN13_PN14.md).
- [Operação, incidentes, testes e reversão](OPERACAO_E_MANUTENCAO.md).

**Limite:** a classificação é um apoio meteorológico consultivo, não um sistema oficial de comunicação de riscos nem um motor automático de decisões sobre aulas.
