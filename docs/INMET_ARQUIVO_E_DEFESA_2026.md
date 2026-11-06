# Integrações com evidência: arquivo anual INMET e publicações da Defesa Civil SC

Atualização técnica: 05/11/2026. A arquitetura **permanece Python + GitHub Actions + GitHub Pages**, sem banco de dados pago, cópia histórica independente ou alteração da política de retenção existente.

## 1. Problema diagnosticado na coleta real

Na execução do GitHub Actions `42152253392` (05/11, UTC 06/11), os conectores se comportaram assim:

| Fonte | Resultado registrado |
|---|---|
| Open-Meteo | 7/7 localidades |
| INMET avisos | `available` |
| NOAA METAR | `available` |
| CPTEC/INPE | `available` |
| NASA POWER | `cached` (dados de publicação anterior) |
| INMET chuva horária | `not_configured` (falta autorização) |
| Cemaden PED | `not_configured` (falta token JWT) |
| Defesa Civil SC | `unavailable` (WordPress/RSS sem resposta utilizável) |

O workflow ter sido concluído com sucesso **não** significa que todas as fontes tenham respondido. A publicação da Defesa Civil SC não possui garantia de API ou SLA; não se pode inferir ausência de avisos a partir de uma falha no feed.

## 2. Nova fonte instrumental oficial: arquivo anual de automáticas INMET

O portal [Dados Históricos Anuais INMET](https://portal.inmet.gov.br/dadoshistoricos) disponibiliza arquivos ZIP anuais com CSVs de estações automáticas (em 05/11/2026, o arquivo de 2026 estava anunciado até 31/10/2026). É **dado observado**, mas **não é chuva atual**. Trata-se de produto diferente de consultas à API de medições recentes, que continuam dependentes de autorização.

Novo módulo `src/observatorio/inmet_archive.py`:

1. Seleciona somente códigos automáticos `Axxx` do catálogo já consultado, limitando a 12 estações do entorno a até 130 km de localidades cadastradas.
2. Baixa, no máximo a cada sete dias em caso de sucesso, o arquivo anual oficial `https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip`; falhas têm retentativa após 24 h. A consulta não executa em build com fixture.
3. Impõe limite de 180 MB para download, 1.600 membros ZIP e 18 MB para cada CSV aberto. **Não extrai arquivos do ZIP**, evitando execução de caminhos contidos nele.
4. Interpreta nomes de colunas e horários UTC; converte decimais com vírgula; trata valores ausentes e não mistura códigos de estação.
5. Publica **até 14 dias em torno da última medição disponível por estação**. Um total diário só aparece quando as **24 horas** da data UTC estão presentes; em cobertura parcial, exibe-se a quantidade de horas medidas e, separadamente, a soma das horas disponíveis.
6. O JSON resultante `data/inmet_archive.json` informa a data exata do dado mais recente, a consulta ao ZIP e a defasagem. É pequeno e compõe **somente o estado de apresentação** no Pages.

**Limites:** o serviço pode oferecer CSVs incompletos ou ser temporariamente indisponível. Não extrapolar leituras pontuais para todo Araquari. A fonte anual não substitui leituras de pluviômetros recentes. A primeira coleta do ZIP real deverá ser validada no runner GitHub após o merge; apenas parsing de fixtures foi testado localmente.

## 3. Defesa Civil SC: recuperação e diagnósticos

O módulo `src/observatorio/defesa_civil_sc.py` agora:

- Prioriza API pública WordPress e RSS por categoria e acrescenta a página institucional de boletins como último caminho permitido, usando somente links HTTPS do domínio oficial.
- Distingue falhas de acesso, HTTP e conteúdo inválido por **códigos de diagnóstico sem credenciais ou URLs privadas**.
- Corrige a conversão de `date` local do WordPress para UTC (`America/Sao_Paulo`), dando prioridade ao `date_gmt` quando disponível.
- Em listagem HTML, extrai **apenas título e data do endereço da publicação**, marcando-a como data aproximada (sem inventar horário).
- Se o serviço estiver inacessível, conserva as publicações oficiais anteriormente obtidas **por até 21 dias** e usa o estado `stale`, com indicação explícita de que a consulta atual falhou. Se não houve publicação válida anterior, mantém `unavailable`.

**Muito importante:** nenhuma publicação de notícia, alerta ou boletim é rotulada como **alerta ativo**, nem ausência de notícia é tratada como ausência de risco. Para emergência, consultar diretamente a [Defesa Civil SC](https://www.defesacivil.sc.gov.br/boletins-do-tempo/), os [alertas oficiais](https://www.defesacivil.sc.gov.br/alerta/) e a Defesa Civil local.

## 4. Comparação entre fontes de previsão

O painel CPTEC/INPE compara a **temperatura máxima prevista** com a previsão Open-Meteo **somente para a mesma data**, indicando diferença em °C. Diferenças entre as fontes não são medições nem indicadores automáticos de perigo. O CPTEC pode usar a localidade mais próxima, o que limita comparabilidade espacial.

## 5. Validação e implantação

```bash
python -m unittest discover -s tests -q
python -m compileall -q src scripts
node --check web/app.js
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --output dist
python scripts/validate_site.py --output dist --fixture
```

O CI remoto deverá executar os mesmos testes. **Após merge**, executar `Update forecast and publish Pages` e conferir na saída `Provider status: ... inmet_archive=... defesa_sc=...`. O primeiro download real do ZIP pode falhar sem prejudicar o site, ficando `unavailable`. Não apresentar sucesso da implantação como sucesso de cada conector.

Como reverter: fazer revert do PR no GitHub; a publicação anterior do Pages permanece utilizável até a próxima implantação. Nenhum arquivo externo, token ou banco é alterado.
