# Inventario inicial de provedores

| Fonte | Endereco oficial | Estado |
|---|---|---|
| Open-Meteo | https://open-meteo.com/en/docs | Integracao implementada para previsoes/estimativas; execucao externa pendente |
| INMET catálogo | https://apitempo.inmet.gov.br/estacoes/T | Integrado: metadados e proximidade, **não medições** |
| INMET avisos | https://apiprevmet3.inmet.gov.br/avisos/ativos | Novo adaptador: avisos por código IBGE; disponibilidade real/contrato do endpoint por confirmar |
| Aviation Weather Center/NOAA | https://aviationweather.gov/data/api/ | Novo adaptador METAR: medições aeronáuticas de SBJV/SBNF; não pluviômetros municipais |
| INMET medições horárias | https://portal.inmet.gov.br/ | Pendente: validar interface pública estável e condições de acesso |
| Epagri/Ciram | https://ciram.epagri.sc.gov.br/dadosambientaispublicos/index.jsp | Download publico sujeito a cadastro; API aberta nao confirmada |
| Defesa Civil SC | https://www.defesacivil.sc.gov.br/ | Links oficiais; dados de alertas ainda nao integrados |
| Cemaden | https://sws.cemaden.gov.br/PED/api/ui/ | API documentada com credenciais |
| ANA/HidroWeb | https://www.snirh.gov.br/hidroweb/ | Confirmar nova API/credenciais |
| CPTEC/INPE | https://servicos.cptec.inpe.br/XML/ | Validar endpoints XML ativos |
| SGB/SACE | https://sace.sgb.gov.br/ | Avaliar cobertura e acesso |
| Marinha | https://www.marinha.mil.br/chm/dados-do-smm | Avaliar produtos publicos |

Para cada fonte futura, validar: cobertura, licenca, autenticacao, quota, data de referencia, frequencia de publicacao, formato, qualidade, possibilidade de redistribuicao e politica de indisponibilidade.

**Atenção:** o adaptador de avisos do INMET usa uma interface não garantida; quando indisponível, o sistema não afirma que não há avisos. METAR mede condições nos aeroportos e não substitui rede de pluviômetros. Não há integração pluviométrica, radar ou hidrológica nesta fase. Ver [Avisos e METAR](AVISOS_E_METAR.md).

## Medições horárias INMET condicionadas a token

Módulo experimental de chuva observada a partir de estações automáticas INMET. Usa somente credencial legítima obtida pelo usuário e guardada em `INMET_API_TOKEN` nos Secrets do GitHub Actions. O padrão de endpoint com token é conhecido por implementações públicas, mas ainda exige validação real no ambiente de implantação. Os dados do INMET são brutos e podem conter marcadores de ausência (`9999`/`Null`). Sem token, o site não publica chuva medida. Mais detalhes em [Chuva e histórico de avisos](CHUVA_E_HISTORICO_AVISOS.md).
