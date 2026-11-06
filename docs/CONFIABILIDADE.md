# Confiabilidade, cobertura e publicação parcial

## Alterações

`pipeline.rain_window` valida 24 intervalos horários consecutivos. O dado Open-Meteo em T é o acumulado da hora anterior: são usados endpoints entre hora UTC corrente +1h e +24h. Não há interpolação da fração da hora em curso. A interface mostra a janela exata. Duplicados iguais não somam duas vezes; conflitos e valores inválidos retiram o intervalo da cobertura. `rain_next_24h_mm` mantém nome e unidade, mas retorna `null` quando incompleto. `rain_window` informa total, soma parcial, limites e contagem.

Cemaden mantém o estado global compatível e acrescenta `status`/`diagnostic` em cada município. Uma falha não pode ser mostrada como consulta bem-sucedida sem estações. O arquivo `coverage.json` inventaria modelos, acumulados Cemaden, sensores próximos e METAR sem confundir os tipos de referência. As contagens são da coleta publicada; referências mais recentes não garantem que todas as leituras tenham a mesma idade.

No navegador, acumulados e pluviometria instrumental são reavaliados pela data da medição e da consulta (6h); sensores Cemaden respeitam 3h20 por leitura e 6h para a consulta. O modelo usa 8h. Horários futuros acima da tolerância de 10 minutos e datas inválidas não são atuais. O estado é reavaliado a cada minuto e ao retornar à página. Isso não aumenta a frequência de coleta.

A coleta do modelo pode produzir um manifesto vazio somente quando `allow_empty=True`; o uso direto conserva o comportamento anterior de falhar. O build completo segue para as outras fontes e publica parcialmente se houver fonte operacional atualizada. Se nenhuma responder, aborta antes de substituir o diretório. O validador exige a indicação parcial e rejeita totais de chuva com cobertura incompleta.

`model_history_published` protege a recuperação do histórico de modelo contra um 404 posterior; não é backup independente. Segredos, autenticação, limite Cemaden e frequência de três horas permanecem nos mecanismos existentes.

## Verificação e reversão

Executar os testes Python, `node tests/web_reliability.cjs`, `compileall`, `node --check`, build offline e `validate_site --fixture`. A validação sem `--fixture` deve rejeitar esse mesmo artefato sintético. Testes adicionais cobrem falha parcial/total, repetição, duplicatas e dados inválidos. Os testes JavaScript usam DOM simulado e não substituem QA visual.

Após integrar, conferir no Actions os estados reais e o Pages em celular/desktop. Validar municípios com e sem observações, falhas municipais e leituras antigas. Não usar fixtures em produção. Para reverter, reverter o commit/PR e republicar pelo workflow existente; não apagar os arquivos históricos publicados. Nenhum histórico externo ou serviço pago foi acrescentado.
