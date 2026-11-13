# Defesa Civil SC: recuperação dos textos qualitativos

Diagnóstico e correção de 13/11/2026. Complementa [Aproveitamento das fontes](APROVEITAMENTO_DAS_FONTES.md).

## Falhas comprovadas

O arquivo publicado registrava `status: unavailable`, com `timeout` em WordPress JSON, três feeds e listagem HTML. O código impunha 8 segundos por requisição. Em consultas reais, o JSON antigo de 35 resumos retornou HTTP 200 em aproximadamente 9 s; o JSON com oito textos completos, em 8,5 s; e a página `/alerta/`, em 9,2 s. Esses tempos são observações da sessão, não garantia de desempenho futuro ou medição de todos os caminhos de rede.

Além do prazo curto, havia três limitações de extração:

- O JSON solicitava `excerpt`, mas não `content`: informações territoriais importantes podiam estar apenas no corpo.
- “Monitoramento Meteorológico DC/SC” e “Observação Meteorológica DC/SC” eram descartados pelo reconhecedor de títulos, embora existissem no retorno oficial.
- O fallback HTML consultava somente `/boletins-do-tempo/`, deixando de tentar primeiro a página específica solicitada pelo usuário: <https://www.defesacivil.sc.gov.br/alerta/>.

O portal oficial respondeu normalmente ao teste; isso não comprova disponibilidade permanente nem permite atribuir os timeouts anteriores a bloqueio geográfico ou autenticação.

## Correção

1. Timeout por requisição de **20 s**. O coletor compartilha um orçamento de 70 s entre as tentativas, reduzindo o timeout ao tempo restante e deixando de iniciar consultas quando ele se esgota. O prazo de socket se aplica às operações de rede; não é uma garantia de tempo total exato em toda condição de rede.
2. JSON principal limitado a **20 publicações**, incluindo texto completo: `date,date_gmt,link,title,excerpt,content`. Resposta limitada a 750 kB. Não exige credencial.
3. Texto completo fornecido pelo JSON ou RSS dispensa a consulta adicional ao artigo. Se faltar, permanecem até duas consultas de artigos, dentro do orçamento. Scripts e estilos são removidos; parágrafos são preservados para interpretar os campos.
4. Reconhecimento dos títulos atuais, incluindo monitoramentos, observações meteorológicas e o travessão dos alertas. As categorias permanecem distintas; monitoramento não é convertido em alerta.
5. Feeds de fallback consultados em paralelo. Se não houver publicações utilizáveis, a listagem específica `/alerta/` precede `/boletins-do-tempo/`.
6. Menções municipais são buscadas no texto completo e por palavras inteiras. Referência a Litoral Norte ou contexto estadual pode aparecer na página detalhada, identificada como **contexto regional, sem confirmação de abrangência municipal**.
7. O conteúdo completo aparece recolhido em **Ler texto da fonte**, com link para o artigo oficial. Nenhum bloco permanente foi adicionado à inicial.

O acesso alternativo `?rest_route=/wp/v2/posts` também respondeu no teste externo ao GitHub, mas não foi adicionado como consulta redundante: ambos dependem do mesmo portal e falharam no runner, conforme a verificação abaixo. O feed `/alerta/feed/` retornou um RSS sem itens na consulta; a integração mantém os feeds das categorias, que não devem ser confundidos com o feed de uma página.

## Prazo do alerta e validade da publicação

Um título como “ATENÇÃO – dd/mm hh:mm – … nas próximas 2 horas” contém um relógio de emissão e uma duração explícitos. O parser usa esse relógio em `America/Sao_Paulo`, combinado com o ano da publicação e verificação de coerência temporal; não usa o instante de publicação como início. Aceita uma duração inteira de 1 a 24 h, sem conflitos entre título e corpo. A publicação deve ocorrer entre 10 minutos antes e seis horas depois do relógio informado; datas incoerentes não geram janela. A virada de ano é conciliada entre dezembro/janeiro.

`event_window` conserva início, fim, duração e a base `explicit_title_clock_and_reported_duration`. O campo legado `validity_status: not_verified_from_publication_date` é mantido: a data de publicação isoladamente continua não comprovando vigência. A janela informada também não confirma cancelamentos ou revisões posteriores.

A validação do artefato recalcula essa janela a partir do título, texto e publicação originais. A análise consultiva só aproveita uma janela ainda válida, consulta original atual, fenômeno positivo e região explicitamente aplicável. A lista de municípios/regiões do corpo é usada; um alerta para o Oeste não vira alerta para Araquari. Publicações sem horário/duração conciliáveis permanecem como contexto, sem inventar validade. Uma expressão genérica como “próximas horas” não é convertida em intervalo.

Foi reproduzido um alerta de 12/11 às 19h24 para Araquari e outros municípios, com duração de duas horas e publicação às 19h28. A janela termina às 21h24 do próprio dia 12; ele pode ser consultado como histórico, mas não elevar o risco do dia 13. Esse exemplo demonstra por que a recuperação dos textos não autoriza tratar todas as publicações retornadas como alertas ativos.

## Verificação e limites

### Impedimento operacional confirmado no GitHub Actions

A publicação do PR #54 passou nos testes e no deploy, mas **a fonte permaneceu indisponível em produção**. Aumentar o timeout corrigiu uma limitação observada no ambiente de diagnóstico; não resolveu a conexão do GitHub com o portal.

No runner Ubuntu do workflow de qualidade, execução `43463813198`, em 13/11/2026 às 16h35 UTC:

| Sondagem | Resultado |
| --- | --- |
| JSON com apenas um link no domínio `www` | Timeout em 12,31 s |
| Mesmo JSON sem `www` | Timeout em 12,56 s |
| API via `?rest_route=` | Timeout em 12,32 s |
| `curl --ipv4`, domínio `www` | DNS respondeu; conexão TCP não concluída em 6 s; nenhum HTTP/TLS |
| `curl --ipv6`, domínio `www` | Nenhum endereço resolvido para essa família |
| Feed federal `https://idapfile.mdr.gov.br/idap/api/rss/cap` | HTTP 200 em 1,13 s, leitura de apenas 1 kB |

O coletor completo também terminou sem publicações nesse runner. A execução de publicação `43462520278` gerou `status: unavailable`. Isso situa a falha antes da extração dos textos e, no teste IPv4, antes do HTTP. Não comprova a causa administrativa da restrição: bloqueio de IP/faixa, firewall e roteamento são hipóteses, não fatos demonstrados. Também não prova disponibilidade completa do feed federal.

### Encaminhamentos para recuperar a coleta automática

1. **Preferência: acesso oficial do runner.** Apresentar à operação do portal os horários e resultados acima e solicitar verificação do acesso HTTPS originado do GitHub Actions. Se houver necessidade de liberação por IP fixo, usar executor controlado com saída fixa; os runners hospedados não oferecem esse controle neste projeto.
2. **Alternativa: coletor em executor controlado com acesso comprovado ao portal.** Manter a mesma normalização, limites, validação e relógios originais. Publicar o artefato por credencial restrita, sem segredos no navegador. Isso exige disponibilizar infraestrutura e testar a rede antes de migrar; não foi implantado nesta correção.
3. **Canal oficial independente: avaliar CAP/IDAP federal.** O registro da autoridade no WMO aponta esse feed, mas a resposta é nacional e muito volumosa. O teste externo excedeu 16 MB antes de terminar. Uma integração precisa confirmar emissor estadual (`senderName`, não apenas `sender` nacional), município/área, validade e referências de atualização/cancelamento, além de obter resposta completa com custo controlado. Não foi incorporado como fallback nem pode ser considerado equivalente às publicações editoriais do portal.

Repetir requisições ao mesmo domínio ou ampliar indefinidamente o timeout não constitui contingência de rede. Enquanto o acesso não for restabelecido, a fonte deve continuar identificada como indisponível/desatualizada; as demais fontes permanecem independentes. Ausência de coleta não é ausência de alerta. As sondagens temporárias não foram mantidas em cada CI para não acrescentar consultas e demora à rotina.

O coletor corrigido foi executado contra o portal oficial: recuperou **20 publicações com texto completo**, em cerca de **8,3 s**, incluindo duas com menção a Araquari, sem diagnósticos de falha. Esse é um teste real de conectividade e extração, separado dos testes sintéticos. Não afirma que existiam alertas locais vigentes.

`tests/test_defesa_recovery.py` cobre timeout configurado, conteúdo completo sem consultas redundantes, títulos atuais, menções no corpo, RSS, janela explícita, alertas encerrados, duração ausente/conflitante, relógio da emissão separado da publicação, fallback `/alerta/` e preservação de consulta anterior sem renovar seus relógios.

Permanecem os limites anteriores: dados territoriais apenas em mapas/imagens não são transformados automaticamente em evidência local; manchetes não comprovam ocorrência de desastre; monitoramentos regionais e avisos de dias futuros não são automaticamente critérios atuais. A cor da Defesa Civil não é convertida diretamente em nível institucional. Falha completa conserva o conteúdo anterior como desatualizado, sem declará-lo atualizado.

O agendamento de 30 minutos, demais coletores, inicial compacta e critérios severos foram preservados. Reversão por revert do commit.
