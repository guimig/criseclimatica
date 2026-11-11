# Algoritmo de classificação dos níveis

A documentação vigente é [Classificação consultiva e inicial objetiva](CLASSIFICACAO_CONSULTIVA.md), método `araquari-risk-v2`.

Ela descreve as categorias da PN 13/2026, os critérios objetivos auxiliares, as fontes e estações, a validade de cada evidência, os avisos Epagri/Ciram e INMET, os requisitos de normalidade, as limitações de calamidade e a cor efetivamente exibida na inicial.

A estrutura das fontes, as estatísticas com pesos iguais, as unidades inferidas e as substituições estão em [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md).

O resultado corrente fica em `data/dashboard.json → risk_classification`. O campo `assessment` anterior permanece para auditoria e não é o cartão de classificação atual.
