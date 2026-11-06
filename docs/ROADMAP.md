# Roadmap de desenvolvimento

## Fase 0 - Concluida localmente, aguardando CI remoto

- Estrutura modular Python e contratos de resposta normalizados.
- Open-Meteo para sete pontos aproximados de SC.
- Interface responsiva com graficos e comparacao regional.
- Arquivos JSON para publicacao via Pages sem commits frequentes.
- Gatilho a cada tres horas, execucao manual e workflow de testes.
- Rotinas portaveis JSONL.GZ com teste de ida e volta.

Criterio de aceite externo: primeira execucao bem-sucedida no GitHub Actions, configuracao GitHub Pages, verificacao do site publicado e da atualizacao real. A execucao externa e independente da bateria de testes sinteticos.

## Fase 1 - Observacoes instrumentais e confiabilidade

1. Catalogo oficial e operacional de estacoes INMET para Araquari e entorno.
2. Confirmar endpoint e licenca para medidas de cada fonte, e nao apenas estacoes catalogadas.
3. Integrar fonte oficial de alertas com territorio/periodo de validade.
4. Painel de observacoes separado do painel de modelo.
5. Fallback preservando ultima publicacao valida para falhas parciais.
6. Revisao de coordenadas e representatividade territorial.

## Fase 2 - Historicos e armazenamento sem banco pago

1. Testar armazenamento autenticado no Google Drive com segredo GitHub.
2. Lotes JSONL.GZ particionados, resumos horarios, diarios e mensais.
3. Criterios de retencao por fonte, escala temporal e uso efetivo.
4. Registrar metadados, latencia, cobertura e indicadores de qualidade.
5. Preservar episodios relevantes e dias normais para comparacoes.
6. Benchmarks de leitura, escrita, recuperacao e uso de armazenamento.

## Fase 3 - Hidrologia, litoral e analise

1. Cemaden e ANA, sujeito a cadastro e credenciais.
2. Epagri/Ciram por modalidade de integracao autorizada.
3. Informacoes de mares, ondas, radar e cobertura de satelite.
4. Comparacao modelo versus estacoes, sem equiparar estimativa a medicao.
5. Catalogo de eventos meteorologicos e anomalias com verificacao.
6. Visao Brasil agregada e consultas sob demanda.
