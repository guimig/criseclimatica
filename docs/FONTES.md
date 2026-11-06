# Inventario inicial de provedores

| Fonte | Endereco oficial | Estado |
|---|---|---|
| Open-Meteo | https://open-meteo.com/en/docs | Integracao implementada para previsoes/estimativas; execucao externa pendente |
| INMET | https://portal.inmet.gov.br/ | Integrar observacoes apos validar endpoints e dados |
| Epagri/Ciram | https://ciram.epagri.sc.gov.br/dadosambientaispublicos/index.jsp | Download publico sujeito a cadastro; API aberta nao confirmada |
| Defesa Civil SC | https://www.defesacivil.sc.gov.br/ | Links oficiais; dados de alertas ainda nao integrados |
| Cemaden | https://sws.cemaden.gov.br/PED/api/ui/ | API documentada com credenciais |
| ANA/HidroWeb | https://www.snirh.gov.br/hidroweb/ | Confirmar nova API/credenciais |
| CPTEC/INPE | https://servicos.cptec.inpe.br/XML/ | Validar endpoints XML ativos |
| SGB/SACE | https://sace.sgb.gov.br/ | Avaliar cobertura e acesso |
| Marinha | https://www.marinha.mil.br/chm/dados-do-smm | Avaliar produtos publicos |

Para cada fonte futura, validar: cobertura, licenca, autenticacao, quota, data de referencia, frequencia de publicacao, formato, qualidade, possibilidade de redistribuicao e politica de indisponibilidade.

**Nao existe nesta fase integracao de alertas oficiais, dados de estacoes, radar nem medicao hidrologica.** Nao derivar avisos de risco de previsoes de modelo.
