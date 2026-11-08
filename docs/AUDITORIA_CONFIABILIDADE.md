# Auditoria de confiabilidade — 08/11/2026

## Evidências da interrupção das 10h47 (Brasília)

A publicação disponível era de 05h31, gerada às `2026-11-08T08:31:37Z`, válida para classificação até `11:31:37Z` (08h31). A mensagem de classificação desatualizada estava correta para essa idade. O problema de origem era a ausência de nova publicação.

O workflow [42463080989](https://github.com/guimig/criseclimatica/actions/runs/42463080989) iniciou às 05h28 e terminou com sucesso às 05h31. Não houve execução posterior registrada até a investigação, apesar do cron anterior de 40 min. Também houve intervalo de aproximadamente 5h36 entre os eventos agendados de `01:46Z` e `07:22Z`. Não eram builds falhos ou bloqueios por autenticação nesses intervalos: faltavam eventos registrados. A causa interna de omissão do GitHub não é exposta pelos registros consultados.

O GitHub documenta que [execuções agendadas podem atrasar ou ser descartadas sob carga](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows), especialmente no início da hora. Portanto um cron não garante pontualidade. A falha de teste CPTEC da noite anterior foi corrigida no PR 31 e não se repetiu nas publicações desta manhã.

## Fontes verificadas na última coleta anterior à correção

| Fonte | Situação observada | Consequência |
| --- | --- | --- |
| Open-Meteo | 20/20 municípios disponíveis | Não causou a interrupção da publicação |
| Cemaden | Araquari disponível, 3 estações; conjunto regional parcial | Falhas em outros municípios não apagam a leitura local |
| NOAA/METAR | Disponível; 4/6 aeródromos com boletim utilizável | Não exige boletim em todos os aeródromos para publicar |
| CPTEC | Disponível | Contexto diário independente; não substitui chuva medida |
| Epagri/Ciram | Cache com consulta original de 04h22; nova verificação às 05h28 | Cache intencional do adaptador, sem renovar a data de consulta original; fonte perde validade após 6 h |
| Defesa Civil SC | API, RSS e página pública falharam no coletor com `URLError` | Limitação complementar, não deve apagar previsão ou Cemaden; diagnóstico passa a distinguir timeout/DNS/TLS/HTTP/conexão quando identificável |
| INMET observado recente | `not_configured`, sem token de acesso | Integração opcional; não foi simulada ou substituída por zero |
| INMET avisos | Disponível | Produto diferente de observações instrumentais; consulta sem aviso não prova normalidade |

Rainha retornava zero e Porto Grande/Centro retornavam acumulados distintos. Esses valores vinham da fonte; não há diagnóstico de hardware que justifique excluir automaticamente uma estação. A mediana mantém extremos e horários visíveis; valores faltantes continuam distintos de zero.

## Correções

1. **Agendamento com reconciliação:** verificação aos minutos 7, 27 e 47. Só pula a coleta agendada quando confirma uma publicação real válida com menos de 35 min, resultando em cerca de 40 min entre coletas quando os eventos chegam regularmente. Eventos perdidos não deslocam um contador local: cada evento verifica a idade publicada. Falha de consulta, formato inválido, futuro implausível ou prazo vencido solicitam coleta. Push/manual forçam coleta. Quando a coleta é dispensada, o deploy também é dispensado; não se publica artefato inexistente.
2. **Atualização no navegador:** home e detalhes verificam novas versões a cada minuto com aba visível, no retorno à aba e na recuperação de conexão, com limite de frequência e exclusão de concorrência. Só recarregam quando a versão aumenta ou falta a primeira leitura. Não consultam serviços autenticados. Seletores da home são preservados.
3. **Falha transitória:** erros de consulta preservam o conjunto já carregado e seus horários. O aviso de conexão não é confundido com chuva zero, falta de dados na origem ou melhora das condições.
4. **Validades coerentes:** publicação/classificação têm referência máxima de 3 h nas duas páginas. Na home, a classificação vencida fica suspensa; medições de até 6 h e previsão com coleta/referência de até 8 h podem continuar nos cartões como “Última leitura”/“Publicação anterior”, com seus períodos originais. Seus prazos não prolongam a classificação nem transformam previsão anterior em uma nova janela de 24 h.
5. **Completude real:** uma fonte marcada como disponível sem acumulados locais utilizáveis de 1 h e 24 h não permite normalidade. `coverage_gaps` identifica as referências que faltam na explicação.
6. **Justificativa do nível:** um nível sustentado por aviso prioritário não é explicado por uma rajada de faixa inferior. Em empate, a base prioritária continua sendo a justificativa. Chuva acumulada e vento que contribuam juntos aparecem no título de atenção. Avisos complementares encerrados não sustentam contexto vigente.
7. **Rastreabilidade de conexão:** a evidência da Defesa Civil informa última tentativa e categorias sanitizadas das falhas. Não se desativa TLS, contorna autenticação ou publica credenciais para recuperar uma fonte.

## Validação e limites

Regressões cobrem agendamento após eventos perdidos, publicação fresca/vencida/inválida, falha de sondagem, atualização automática em navegador real, perda/retorno de conexão, não regressão de versão CDN, permanência dos seletores, validades independentes, ausência de acumulados sem falso verde, prioridade da justificativa e categorias de falha sem vazamento de texto privado. A suíte de publicação e os testes de desktop/celular continuam obrigatórios.

O novo agendamento reduz a dependência de um único evento, mas continua no mesmo serviço e pode sofrer omissões. Garantia mais forte de periodicidade exige um disparador externo ou hospedagem com agendador independente, ainda não configurados. O painel não mascara essa limitação ampliando o prazo da classificação. Indisponibilidade de um portal externo permanece identificada como limitação da fonte, e não como integração recuperada sem evidência.

As faixas de chuva/vento, a prioridade institucional, as restrições territoriais, os históricos e os critérios para não atribuir vermelho/roxo por picos numéricos foram preservados. Ver [algoritmo completo](ALGORITMO_CLASSIFICACAO_NIVEIS.md).
