# Guia da documentação

**Estado de referência:** branch \`main\` examinada em 14/11/2026 (commit \`3ec7bb9\`). Este índice descreve a implementação conhecida nessa data; disponibilidade de serviços e resultados meteorológicos devem ser verificados a cada ciclo.

## Comece por aqui

| Pergunta | Documento de referência |
| --- | --- |
| O que é o Observatório, o que mostra e quais são seus limites? | [README](../README.md) |
| Como as peças interagem, onde estão as entradas e saídas? | [Arquitetura](ARQUITETURA.md) |
| Como implantar, acompanhar os ciclos, investigar falhas e reverter? | [Operação e manutenção](OPERACAO_E_MANUTENCAO.md) |
| Quais arquivos JSON existem, como verificar identidade, validade e histórico? | [Contratos de dados e retenção](CONTRATOS_DADOS_E_HISTORICOS.md) |
| Quais provedores estão implementados e o que cada um pode demonstrar? | [Inventário de fontes](FONTES.md) |
| Como é calculado o nível consultivo vigente? | [Algoritmo e pontos de auditoria](ALGORITMO_CLASSIFICACAO_NIVEIS.md) e [classificação consultiva v4](CLASSIFICACAO_CONSULTIVA.md) |
| Como funciona o aproveitamento cruzado de fontes? | [Aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md) e [interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) |
| O que está pronto, pendente ou condicionado a acesso externo? | [Roadmap](ROADMAP.md) |
| Quais escolhas arquiteturais precisam ser preservadas? | [Decisões](DECISOES.md) |

## Documentação de operação especializada

- [Agendamento primário cron-job.org e reserva GitHub](ATUALIZACOES_30_MINUTOS.md).
- [Autenticação e limites do Cemaden/PED](CEMADEN_PED_AUTENTICACAO.md).
- [Estação meteorológica do IFC Araquari](ESTACAO_IFC_ARAQUARI.md).
- [Coleta qualitativa da Defesa Civil SC e limitação do runner](DEFESA_CIVIL_COLETA_QUALITATIVA.md).
- [Previsão municipal INMET e recuperação](INMET_PREVISAO_E_RECUPERACAO.md).
- [Comparação de modelos](COMPARACAO_DE_PREVISOES.md).
- [Estações Cemaden e METAR](AMPLIACAO_ESTACOES.md).
- [Referência normativa e painel](PAINEL_ARAQUARI_PN13_PN14.md).

## Relatórios e documentos de evolução

Existem outros relatórios de investigação em \`docs/\`, como \`AUDITORIA_CONFIABILIDADE.md\`, \`AUDITORIA_GERAL_2026_11_08.md\`, \`REVISAO_APLICACAO_2026_11_08.md\`, \`INTEGRACOES_V9.md\` e \`RECUPERACAO_PUBLICACAO_2026_11_09.md\`. Eles são **registros datados de uma etapa**, não inventários atuais. Contagens de testes, políticas de agendamento, indisponibilidades e pendências nesses registros retratam seu próprio período.

Quando houver divergência, consulte nesta ordem: **código e workflows da \`main\` em execução → produtos JSON daquela publicação → documentos de referência atualizados → relatórios históricos**. A página pública pode estar defasada por falha de coleta, deploy ou propagação de cache. Um PR ainda não integrado não descreve produção.

## Escopo e cautelas

O site é um **apoio consultivo**, não uma central oficial de alerta, um sistema de comando da Defesa Civil, nem um registro automático de suspensão de aulas. As seis categorias da referência institucional não significam seis níveis oficialmente emitidos pelo aplicativo. A presença de um coletor no código não comprova acesso ao provedor em produção.

As cópias das Portarias Normativas nº 13 e 14/2026 em \`web/references/\` e os critérios registrados em [PN 13/14](PAINEL_ARAQUARI_PN13_PN14.md) não substituem interpretação e decisão da autoridade competente. Alteração de regra institucional exige validação humana antes de se tornar comportamento do sistema.

## Para atualizar a documentação

1. Leia a implementação da \`main\`, os testes e o último workflow. Não atualize status apenas porque uma integração foi proposta.
2. Distinga **implementado**, **operacional comprovado em ciclo identificado**, **condicionado** e **planejado**.
3. Documente fonte, unidade, referência temporal, validade, abrangência e comportamento na falha; não equipare ausência de leitura a zero.
4. Atualize os documentos de referência e este índice; preserve relatórios datados com uma nota de supersessão, em vez de apagar a investigação.
5. Abra PR com apenas documentação, verifique links relativos e registre o SHA revisado. Não mescle documentação com mudança funcional sem necessidade.
