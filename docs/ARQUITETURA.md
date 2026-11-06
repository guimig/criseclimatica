# Arquitetura e decisao de armazenamento

## Decisoes consolidadas

- Python processa fontes em GitHub Actions. GitHub Pages publica exclusivamente artefatos estaticos.
- Nenhum banco de dados pago, Google Sheets ou backend web dedicado e necessario na fase 0.
- Os dados carregados no navegador sao o ultimo conjunto **publicado**, nao necessariamente a leitura mais atual da API.
- Os campos `measurement_status`, `source.kind`, `current.time` e `collected_at` separam estimativa, horario da referencia e horario da coleta.
- Cada fonte futura devera possuir um adaptador que nao dependa do codigo do frontend.

## Fluxo

```text
Open-Meteo (modelo) --HTTPS--> Python adapter
       --> normalize + verify timestamp/units
       --> site/data/latest.json + site/data/places/{id}.json
       --> Pages artifact --> static browser
```

O build utiliza um diretorio temporario e apenas substitui a pasta de destino se houver ao menos um municipio valido. Se todas as consultas Open-Meteo falharem, o build segue para as fontes independentes e pode publicar parcialmente. Se todas as fontes operacionais falharem, o workflow para antes da publicação. Se somente parte falhar, o manifesto informa indisponibilidade por localidade.

## Camadas independentes adicionadas

O processo publica `data/alerts.json` (avisos INMET por código IBGE) e `data/observations.json` (boletins METAR de aeródromos próximos), sem alterar os contratos dos modelos já publicados. A indisponibilidade das fontes secundárias é representada explicitamente e **não bloqueia** a publicação das estimativas válidas. Uma ausência de avisos só é declarada quando a consulta ao INMET foi bem-sucedida e recente.

Ver [Avisos e METAR](AVISOS_E_METAR.md) para segurança, limites, unidades e tempos.

## Dados publicados

- `data/latest.json`: fonte, tipo, hora de coleta, status e leituras resumidas por localidade.
- `data/places/{id}.json`: corrente modelada, previsao horaria, previsao diaria e metadados.
- `schema_version`: versao para permitir evolucao do contrato.

As coordenadas dos pontos de referencia sao aproximadas. O catalogo nao e um inventario de estacoes.

## Arquivo historico (proximo ciclo)

O modulo `storage.py` suporta escrita atomica de JSON, substituicao atomica de particionamentos JSONL.GZ e leitura limitada. Esses utilitarios sao testados, mas **nenhum workflow ainda envia ou acumula historicos em Drive**.

Politica proposta para validar em benchmark:

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
