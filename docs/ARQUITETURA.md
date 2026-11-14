# Arquitetura e armazenamento — referência consolidada em 14/11/2026

> **Leitura do documento:** as seções datadas de 08–11/11 registram a evolução do sistema. Para a arquitetura em execução, prevalecem os componentes listados abaixo, os [contratos atuais](CONTRATOS_DADOS_E_HISTORICOS.md) e o [manual de operação](OPERACAO_E_MANUTENCAO.md). Trechos antigos sobre o INMET não representam mais a classificação consultiva v4.

> Atualização de 11/11/2026: [Interpretação multifontes](INTERPRETACAO_MULTIFONTES.md) documenta a síntese meteorológica atual, pesos iguais das quatro estações, participação do INMET nas previsões e avisos, substituições e hipóteses de unidades. Restrições anteriores de apresentação não descrevem essa nova camada. A correspondência normativa permanece separada e conserva seus critérios.


## Arquitetura atual verificada

`cron-job.org (00/30) → workflow_dispatch → pages.yml → testes → build_site.py → adaptadores Python → síntese multifontes → risk_classification v4 → JSON/HTML/CSS/JS temporários → validate_site.py → artefato Pages → deploy`.

- `schedule` GitHub nos minutos 7 e 37 atua como reserva por idade (25 min); `push` e `workflow_dispatch` forçam coleta.
- `config/locations.json` define 20 pontos de consulta em SC/PR; a classificação principal é de Araquari.
- `src/observatorio/risk_classification.py` implementa `araquari-risk-v4`, calculado após a síntese `multisource.py`; `assessment` legado não é o cartão consultivo vigente.
- A previsão municipal INMET **participa** de evidências qualitativas e guarda extremos diários quantitativos, sem inventar séries horárias. CPTEC e previsões editoriais podem contribuir sob elegibilidade própria. Veja [aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md).
- O coletor Defesa Civil SC está implementado, mas a conectividade ao portal falhou no runner diagnosticado em 13/11; isso não torna as demais fontes indisponíveis.
- Fonte, instante de medição, instante de coleta, vencimento e identidade de publicação não são intercambiáveis. A saída `dist/data/` é gerada, não uma base versionada em commits.

A visão operacional e os comandos estão em [Operação e manutenção](OPERACAO_E_MANUTENCAO.md), o inventário gerado em [Contratos de dados](CONTRATOS_DADOS_E_HISTORICOS.md), e o [índice](INDICE.md) separa referências atuais de registros históricos.

## Decisoes consolidadas

- Python processa fontes em GitHub Actions. GitHub Pages publica exclusivamente artefatos estaticos.
- Não há banco de dados pago, Google Sheets ou backend web dedicado na arquitetura atual.
- Os dados carregados no navegador sao o ultimo conjunto **publicado**, nao necessariamente a leitura mais atual da API.
- Os campos `measurement_status`, `source.kind`, `current.time` e `collected_at` separam estimativa, horario da referencia e horario da coleta.
- Cada fonte futura devera possuir um adaptador que nao dependa do codigo do frontend.

## Fluxo

Os adaptadores Python consultam modelos, estações, avisos e produtos históricos separadamente. Normalização, validação de unidades/horários e síntese geram um diretório temporário com JSON e os arquivos de `web/`. O validador confere os contratos e as dependências HTML antes da troca da saída local. O Actions valida novamente o resultado, envia o artefato e o publica no Pages.

Se todas as consultas Open-Meteo falharem, fontes operacionais independentes ainda podem sustentar publicação parcial. Se todas as fontes operacionais falharem, o build preserva a saída anterior. Catálogos isolados não justificam uma publicação aparentemente atualizada. Contratos, dados sintéticos em produção ou dependências HTML inválidos impedem a substituição da saída.

O diretório de saída não pode ser o código-fonte, uma pasta protegida do projeto, um ancestral do repositório ou um link simbólico. A troca usa renomeações no mesmo sistema de arquivos e restaura a pasta anterior se a instalação da nova pasta falhar. A publicação remota permanece a cargo do Pages; essa troca local não é um banco ou backup independente.

## Atualização e consistência no navegador

Home, dados detalhados e comparação de modelos consultam versões publicadas com `cache: no-store`. O módulo `publication-refresh.js` limita frequência/concorrência e verifica versões novas quando a aba está visível. Nenhuma credencial de provedor chega ao navegador. O botão de atualizar recarrega o Pages; não dispara o coletor.

`latest.json` e `dashboard.json` devem ter o mesmo `generated_at`. O arquivo municipal deve corresponder ao `collected_at` indicado no resumo: uma divergência durante a propagação CDN gera uma nova tentativa limitada, sem misturar temperaturas de um arquivo anterior com chuva de outro resumo. Uma falha transitória pode preservar uma leitura anterior da mesma publicação e município, sempre sujeita à validade original. Respostas anteriores não regridem a versão carregada.

Na home, falhas de rede, HTTP/JSON ou identidade da publicação permitem uma segunda leitura completa com chave de cache nova, mantendo a validação de identidade. Depois de duas falhas, a leitura verificada anterior é preservada e o polling continua; o sucesso de `latest.json` sozinho não encerra uma recuperação pendente. Quando nenhuma publicação chegou a carregar, a interface informa indisponibilidade de carregamento, sem afirmar que uma leitura perdeu validade ou foi preservada. Veja [diagnóstico e regressões de 09/11](RECUPERACAO_PUBLICACAO_2026_11_09.md).

A comparação detalhada tem seu próprio conjunto versionado e acompanha as atualizações mantendo variável e período escolhidos. Um conjunto malformado ou uma divergência de versão não apaga uma comparação anterior ainda válida nem interrompe o restante da página.

Arquivos secundários que falhem ao carregar ou não correspondam ao contrato deixam a carga marcada como incompleta. O polling tenta novamente mesmo quando o manifesto continua com a mesma versão. Dados anteriores só são reaproveitados se pertencerem à mesma publicação e conservam seus horários/validades. Um corpo válido que informa fonte indisponível é aceito normalmente: ele não é confundido com falha de download nem gera novas consultas autenticadas.

Se apenas o arquivo municipal ficou pendente, a tentativa automática consulta esse arquivo, sem repetir todos os arquivos secundários. O resumo e os conjuntos secundários são aceitos juntos após a carga, reduzindo a janela de mistura durante consultas concorrentes. Datas de publicação mais de dez minutos à frente do relógio do cliente são recusadas antes de substituir a versão aceita.

O cron-job.org aciona coleta por `workflow_dispatch` aos minutos 00 e 30, todos os dias e horários. O cron GitHub aos minutos 7 e 37 é reserva, com reconciliação por idade de 25 minutos; disparos externos, manuais e pushes sempre coletam. Essa separação evita duplicação recorrente. O pipeline ainda depende da disponibilidade dos runners e fontes. Consulte [a auditoria de confiabilidade](AUDITORIA_CONFIABILIDADE.md) e [o algoritmo completo](ALGORITMO_CLASSIFICACAO_NIVEIS.md) para prazos e limitações.

## Camadas independentes adicionadas

O processo publica `data/alerts.json` (avisos INMET por código IBGE) e `data/observations.json` (boletins METAR de aeródromos próximos), sem alterar os contratos dos modelos já publicados. A indisponibilidade das fontes secundárias é representada explicitamente e **não bloqueia** a publicação das estimativas válidas. Uma ausência de avisos só é declarada quando a consulta ao INMET foi bem-sucedida e recente.

Ver [Avisos e METAR](AVISOS_E_METAR.md) para segurança, limites, unidades e tempos.

## Dados publicados

- `data/latest.json`: fonte, tipo, hora de coleta, status e leituras resumidas por localidade.
- `data/places/{id}.json`: corrente modelada, previsao horaria, previsao diaria e metadados.
- `schema_version`: versao para permitir evolucao do contrato.

As coordenadas dos pontos de referencia sao aproximadas. O catalogo nao e um inventario de estacoes.

## Históricos atuais e armazenamento externo adiado

O Pages recupera e mantém históricos compactos da publicação anterior: snapshots diários de modelo e avisos por até 366 dias; observações por estação e previsões por coleta por sete dias; episódios de estados amostrados com limites próprios de tamanho. Snapshot de modelo não é observação, e duração entre coletas não prova duração contínua de desastre. Os contratos rejeitam desaparecimento ou corrupção de um histórico já marcado como publicado.

O modulo `storage.py` suporta escrita atomica de JSON, substituicao atomica de particionamentos JSONL.GZ e leitura limitada. Esses utilitarios sao testados, mas **nenhum workflow ainda envia ou acumula historicos em Drive**.

Política anterior para eventual armazenamento externo, **ainda em estudo**, sem substituir as retenções já implementadas:

| Camada | Retencao inicial em estudo | Armazenamento |
|---|---|---|
| Atual | Ultima publicacao | Pages JSON |
| Detalhada | 7 dias | JSONL.GZ externo |
| Horaria | 30 dias | JSONL.GZ externo |
| Diaria/mensal | Longo prazo | Resumos compactos |
| Eventos relevantes | Longo prazo | Serie detalhada + indices |

NUNCA confundir uma previsao retrospectiva do modelo com uma medicao de pluviometro. A funcao `daily_index` rotula explicitamente os registros como snapshots do modelo.

## Melhorias planejadas de consistencia

- Persistencia externa com credenciais somente em GitHub Actions Secrets, nao no browser.
- Escrita em lote, indices por periodo/fonte/estacao, hash e arquivos imutaveis apos fechamento.
- Janelas para dados atrasados e reprocessamento idempotente.
- Separacao de valores observados, previstos e estimados por reanalise.
- Alertas oficiais completos com emissor, vigencia e area; nunca alertas inventados.
- Indicadores de cobertura, ausencia de dado e qualidade da medicao.

## Restricoes e recuperacao

GitHub Actions `schedule` nao e um relogio exato; pode atrasar ou deixar de executar. Em repositorios publicos sem atividade, agendas podem ser desativadas. O portal precisa indicar a defasagem dos dados. O site nao deve ser utilizado como fonte unica para decisoes de protecao civil.

Se um provedor alterar o esquema, o adaptador deve falhar de forma explicita, sem publicar valores com unidades incorretas. As ferramentas Python de arquivo devem sempre gravar em arquivo temporario e substituir o destino somente apos escrita completa.

## Extensões opcionais: chuva medida e arquivo de avisos

`observatorio.inmet_rain` acessa, somente quando autorizado e configurado, registros horários brutos de estações INMET, com seleção regional limitada, validação de ausência e indicação de cobertura. `observatorio.notice_archive` consolida a presença de avisos oficiais em arquivos pequenos de longa duração, mas **não** converte avisos em eventos ocorridos. O pipeline publica `data/rain_gauges.json` e `data/notice_history.json`. Os arquivos anteriores são consultados no Pages com tratamento estrito para falhas; não constituem backup permanente.


## Confiabilidade e cobertura por localidade

O build publica `data/coverage.json`, preserva os contratos existentes e adiciona janela/completude à previsão de chuva e diagnóstico municipal Cemaden. A interface reavalia a idade das referências. O manifesto marca `publication_status=partial` quando o modelo não cobre todas as localidades; uma publicação sem nenhum modelo exige outra fonte operacional disponível. O histórico diário marcado como previamente publicado não pode desaparecer silenciosamente. Consulte [Confiabilidade](CONFIABILIDADE.md). Armazenamento externo permanece adiado.


## Identidade do artefato entre arquivos

Cada JSON publica `publication_at`, igual ao `generated_at` de `latest.json`, independentemente de seus horários de coleta/medição. A validação do build rejeita combinações divergentes. A página detalhada exige essa identidade nas fontes secundárias e arquivos municipais quando o manifesto contém o campo; respostas incompatíveis acionam a recuperação automática. O formato anterior sem o campo continua legível para compatibilidade.

A home tenta novamente o histórico observado incompleto da mesma publicação, preservando apenas cache de versão correspondente. A expiração da publicação atualiza a indicação dos gráficos sem exigir interação. Ver [auditoria geral](AUDITORIA_GERAL_2026_11_08.md).

## Estação IFC Araquari (09/11/2026)

`campus_station.py` consulta o dispositivo público do campus em janelas delimitadas e publica `campus_station.json` com a identidade do artefato. `campus-station.js`/`.css` exibem a mesma seção nas duas páginas, com atualização e validade independentes. O produto não é passado ao motor de classificação, à síntese normativa ou à mediana das estações. Detalhes em [ESTACAO_IFC_ARAQUARI.md](ESTACAO_IFC_ARAQUARI.md).

## INMET municipal e avisos (10/11/2026)

`inmet_forecast.py` coleta a previsão municipal JSON de Araquari, isolada em `inmet_forecast.json` e na comparação de fontes. `forecasts.js` apresenta dias/turnos e extremos das 24 amostras horárias do Open-Meteo do mesmo dia de Brasília. O produto passou a participar qualitativamente da classificação consultiva nas versões v3/v4, quando elegível. A frase anterior deste registro datado não descreve o estado vigente; veja [Classificação consultiva](CLASSIFICACAO_CONSULTIVA.md). A recuperação de avisos mantém status de falha e preserva separadamente apenas avisos anteriores com validade explícita ainda não encerrada. [Detalhes](INMET_PREVISAO_E_RECUPERACAO.md).
