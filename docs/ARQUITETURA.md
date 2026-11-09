# Arquitetura e armazenamento — estado atual em 08/11/2026

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

A comparação detalhada tem seu próprio conjunto versionado e acompanha as atualizações mantendo variável e período escolhidos. Um conjunto malformado ou uma divergência de versão não apaga uma comparação anterior ainda válida nem interrompe o restante da página.

Arquivos secundários que falhem ao carregar ou não correspondam ao contrato deixam a carga marcada como incompleta. O polling tenta novamente mesmo quando o manifesto continua com a mesma versão. Dados anteriores só são reaproveitados se pertencerem à mesma publicação e conservam seus horários/validades. Um corpo válido que informa fonte indisponível é aceito normalmente: ele não é confundido com falha de download nem gera novas consultas autenticadas.

Se apenas o arquivo municipal ficou pendente, a tentativa automática consulta esse arquivo, sem repetir todos os arquivos secundários. O resumo e os conjuntos secundários são aceitos juntos após a carga, reduzindo a janela de mistura durante consultas concorrentes. Datas de publicação mais de dez minutos à frente do relógio do cliente são recusadas antes de substituir a versão aceita.

O cron programa coleta aos minutos 7 e 37, em todas as horas e dias, sem dispensa por idade da publicação. A execução do pipeline e o serviço de agendamento não oferecem garantia de pontualidade. Consulte [a auditoria de confiabilidade](AUDITORIA_CONFIABILIDADE.md) e [o algoritmo completo](ALGORITMO_CLASSIFICACAO_NIVEIS.md) para prazos e limitações.

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
