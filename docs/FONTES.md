# Inventário de provedores — implementação e limites

> **Estado de referência (14/11/2026):** a tabela inicial abaixo é um registro histórico de integração. A classificação de cada fonte deve ser conferida no código, em [Aproveitamento das fontes v4](APROVEITAMENTO_DAS_FONTES.md) e no JSON da publicação consultada. **Integrado em código não significa acessível no runner ou com dados elegíveis.** O coletor Defesa Civil SC está implementado, mas seu portal falhou na conexão a partir do GitHub Actions na verificação de 13/11. [Diagnóstico completo](DEFESA_CIVIL_COLETA_QUALITATIVA.md).

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


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

**Nota histórica:** os estados de integração listados na tabela inicial são da fase original e podem estar superados. O adaptador de avisos do INMET usa uma interface não garantida; quando indisponível, o sistema não afirma que não há avisos. METAR mede condições nos aeroportos e não substitui rede de pluviômetros. Há integração pluviométrica Cemaden e adaptador INMET recente condicionado a credencial; radar e hidrologia avançada não são tratados como integrados. Ver [Aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md). Ver [Avisos e METAR](AVISOS_E_METAR.md).

## Medições horárias INMET condicionadas a token

Módulo experimental de chuva observada a partir de estações automáticas INMET. Usa somente credencial legítima obtida pelo usuário e guardada em `INMET_API_TOKEN` nos Secrets do GitHub Actions. O padrão de endpoint com token é conhecido por implementações públicas, mas ainda exige validação real no ambiente de implantação. Os dados do INMET são brutos e podem conter marcadores de ausência (`9999`/`Null`). Sem token, o site não publica chuva medida. Mais detalhes em [Chuva e histórico de avisos](CHUVA_E_HISTORICO_AVISOS.md).

## Extensão de fontes — validação prioritária

| Fonte | Integração | Observações |
|---|---|---|
| NASA POWER Daily | `src/observatorio/nasa_power.py` | API pública de estimativas diárias em grade para ponto de Araquari; dados `PRECTOTCORR/T2M` **não medidos em estação**, atualização diária, estado de cache/falha |
| Cemaden PED | `src/observatorio/cemaden.py` | Endpoint `/pcds-acum/acumulados-recentes` conforme Swagger oficial; exige JWT em segredo `CEMADEN_PED_TOKEN`; registros de pluviômetros municipais, não média municipal |
| INMET pluviometria | `src/observatorio/inmet_rain.py` | Diagnosticados `not_configured`, `access_restricted`, `no_recent_data`, `unavailable`; requer autorização e confirmação de endpoint estável |

**Não confundir:** o catálogo INMET não contém medições, o produto NASA não é pluviômetro, e os boletins METAR não fornecem acumulados de precipitação diária. Referências e instruções em [Integrações](INTEGRACOES_FASE_ATUAL.md).

## Catálogos INMET e Defesa Civil SC (nova integração)

| Fonte | Documentação/página oficial | Estratégia |
|---|---|---|
| INMET estações automáticas | https://portal.inmet.gov.br/paginas/catalogoaut | Metadados da API `/estacoes/T`; sem medições |
| INMET estações convencionais | https://portal.inmet.gov.br/paginas/catalogoman | Metadados da API `/estacoes/M`; sem medições |
| INMET tabela por estação | https://tempo.inmet.gov.br/TabelaEstacoes/A001 | Link oficial para consulta humana; frontend depende de JS, não há contrato confirmado de API |
| BDMEP INMET | https://bdmep.inmet.gov.br/ | Consulta histórica interativa; não usada como coleta automática |
| Defesa Civil SC | https://www.defesacivil.sc.gov.br/boletins-do-tempo/ | Adaptador experimental de publicações WordPress/RSS, com controle de indisponibilidade |
| Defesa Civil SC — alertas | https://www.defesacivil.sc.gov.br/alerta/ | Consulta oficial, sem supor vigência dos posts |
| Defesa Civil Araquari | https://araquari.atende.net/subportal/secretaria-de-seguranca-publica-e-defesa-civil | Página institucional de acesso; feed automático não confirmado |
| CPTEC/INPE XML | https://servicos.cptec.inpe.br/XML/ | Previsões em XML por coordenadas, com validação de estado e datas; sujeito a disponibilidade HTTPS |
| Epagri/Ciram | https://ciram.epagri.sc.gov.br/agroconnect/ | Link oficial ao monitoramento; coleta automatizada ainda depende de validação |

Não buscar contornar bloqueios/recaptcha do INMET ou reutilizar cookies de sessões humanas.


## INMET anual (observações históricas com atraso)

Fonte primária: https://portal.inmet.gov.br/dadoshistoricos .
Pacote anual (2026): https://portal.inmet.gov.br/uploads/dadoshistoricos/2026.zip .
O pacote é de **leituras de estações automáticas**, não de medições atuais;
consulte a indicação de cobertura no portal. O projeto usa o catálogo oficial
para localizar estações, não o portal BDMEP para automatizar uma sessão humana.
Módulo: `src/observatorio/inmet_archive.py`.

Defesa Civil SC: https://www.defesacivil.sc.gov.br/boletins-do-tempo/ .
O conector WordPress/RSS/HTML oficial é experimental; estados `unavailable`
e `stale` não equivalem a ausência de risco. Nenhum CAPTCHA, cookie ou login
é contornado. Consulte a documentação de integração do período.


### Epagri: novas integrações regionais (etapa 8)

- **ArcGIS — Estações ativas atuais:** https://gis.epagri.sc.gov.br/arcgis/rest/services/Zoneamento/Potencial_estacoes/MapServer/1. Integração de **cadastro geográfico**, sem validação de operação recente ou acesso a leituras.
- **Avisos meteorológicos Epagri/Ciram:** https://ciram.epagri.sc.gov.br/index.php/category/avisos-meteorologicos/feed/ e https://ciram.epagri.sc.gov.br/index.php/avisos-meteorologicos/. Publicações com períodos e regiões apresentados somente quando explícitos no RSS; jamais extrapolar avisos de região para município.
- **INMET histórico anual:** https://portal.inmet.gov.br/dadoshistoricos. Além do catálogo automático, a identificação de estação pode vir do cabeçalho de CSV oficial dentro do próprio ZIP, desde que código e coordenadas sejam verificáveis.

Acessibilidade externa comprovada documentalmente não substitui verificação de execução no GitHub Actions.
