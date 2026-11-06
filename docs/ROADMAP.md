# Roadmap de desenvolvimento

## Fase 0 - Publicada no GitHub Pages

- Estrutura modular Python e contratos de resposta normalizados.
- Open-Meteo para sete pontos aproximados de SC.
- Interface responsiva com graficos e comparacao regional.
- Arquivos JSON para publicacao via Pages sem commits frequentes.
- Gatilho a cada tres horas, execucao manual e workflow de testes.
- Rotinas portaveis JSONL.GZ com teste de ida e volta.

O usuario confirmou a publicacao e o funcionamento do site. A comprovacao de ciclos regulares da coleta real em GitHub Actions continua relevante.

## Fase 1 - Observacoes instrumentais e confiabilidade

1. **Implementado em PR:** catalogo publico de estacoes INMET (metadados e proximidade; nao medidas).
2. **Implementado:** avisos do INMET associados por código municipal IBGE, com estado de indisponibilidade e sem inferência de fuso.
3. **Implementado:** boletins METAR dos aeroportos SBJV/SBNF, com identificação da estação e conversão de unidades.
4. **Parcial:** adaptador opcional de precipitação horária INMET desenvolvido; exige token e validação real. Integrações Cemaden/Epagri seguem pendentes.
5. **Implementado:** falhas de avisos, METAR e do adaptador INMET não paralisam a previsão e são identificadas na interface.
6. Revisao de coordenadas e representatividade territorial.

## Fase 2 - Historicos e armazenamento sem banco pago

1. Testar armazenamento autenticado no Google Drive com segredo GitHub.
2. **Parcial:** historico compacto de uma estimativa de modelo publicada por dia no Pages (366 dias), sem confundir com medidas; JSONL.GZ externo ainda pendente.
3. Criterios de retencao por fonte, escala temporal e uso efetivo.
4. Registrar metadados, latencia, cobertura e indicadores de qualidade.
5. **Parcial:** arquivo progressivo de avisos oficiais, que não deve ser interpretado como catálogo de desastres confirmados; séries detalhadas de episódios medidos ainda pendentes.
6. Benchmarks de leitura, escrita, recuperacao e uso de armazenamento.

## Fase 3 - Hidrologia, litoral e analise

1. Cemaden e ANA, sujeito a cadastro e credenciais.
2. Epagri/Ciram por modalidade de integracao autorizada.
3. Informacoes de mares, ondas, radar e cobertura de satelite.
4. Comparacao modelo versus estacoes, sem equiparar estimativa a medicao.
5. Catalogo de eventos meteorologicos e anomalias com verificacao.
6. Visao Brasil agregada e consultas sob demanda.

Ver [Histórico e estações](HISTORICO_E_ESTACOES.md) para a distinção entre catálogo INMET, observações e estimativas de modelo.

Para esta fase, consultar [Avisos INMET e METAR](AVISOS_E_METAR.md).

Ver também [Chuva observada e histórico de avisos](CHUVA_E_HISTORICO_AVISOS.md).
