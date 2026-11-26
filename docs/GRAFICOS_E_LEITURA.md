# Gráficos: leitura, intervalos e cobertura

Atualização: 26/11/2026. Implementação das quatro etapas do plano de melhoria do painel.

## Representação dos dados

Os dois gráficos da inicial permanecem visíveis, com variáveis independentes e um período comum. Cada painel explicita se a janela abrange as últimas ou as próximas horas. O filtro ativo, a última medição e a referência da previsão ficam junto ao desenho. A atualização geral da página não renova o horário das fontes.

Acumulados observados de 1 ou 24 horas são janelas móveis: cada valor é desenhado no término da leitura. Não se usam retângulos ocupando toda a janela móvel nem se somam acumulados sucessivos. A linha é um guia entre amostras próximas, sem criar registros intermediários: o limite visual de continuidade é 60 minutos para Cemaden, 90 minutos para METAR e 10 minutos para as amostras IFC agrupadas em cinco minutos. Intervalos maiores interrompem o traço. Esses limites são de apresentação, não de validade meteorológica ou classificação de risco.

“Por estação” conserva as últimas amostras e seus horários próprios. Valores zero têm comprimento zero, com número visível na coluna de valores. A mesma consulta por toque, teclado e fixação é usada nessa vista e nas séries temporais.

Chuva prevista usa intervalos horários não sobrepostos. A resolução visual parte de 1 h para 24 h, 3 h para 72 h e 6 h para horizontes maiores; pode subir para 6, 12 ou 24 h quando vários modelos dividem uma largura pequena. O título/descrição informa o agrupamento. Só blocos completos recebem barras: ausência, valores inválidos ou duplicatas conflitantes não produzem um total completo. Somas parciais são identificadas no tooltip, com cobertura numérica. O primeiro intervalo pode incluir a hora em curso; consultar os horários de início e término, não interpretar como “próxima hora inteira”.

Zero previsto recebe uma marca na base, sem altura positiva. Faixas neutras indicam intervalos sem cobertura ou cobertura parcial. Nas observações, faixas neutras indicam trechos de pelo menos uma hora sem amostras próximas, considerando a tolerância visual de cada série; não representam duração comprovada de falha da estação. O histórico observado continua limitado a até sete dias e não é reconstruído ao selecionar dez dias.

Temperatura e vento usam linhas segmentadas. A cor e o marcador são determinados pelo identificador da estação/modelo; trocar filtros ou a disponibilidade das demais séries não troca a identidade da estação. Vento e rajada compartilham a cor da estação e se distinguem pelo traçado. As legendas reproduzem os padrões. As cores não classificam o risco de cada estação.

## Escalas e limites de interpretação

Chuva e vento partem de zero. Temperatura usa escala adaptada, com valores de eixo explícitos. Escalas dos dois painéis só são compartilhadas quando variável e janela forem compatíveis; chuva prevista agrupada não compartilha a escala de um acumulado observado de duração diferente.

Uma faixa entre modelos não é probabilidade, e comparação visual com estações não mede acurácia. As previsões diárias/por turno INMET e CPTEC permanecem em seus produtos próprios. Não há interpolação de períodos diários para inventar observações ou previsões horárias.

O vencimento de uma variável é reavaliado enquanto a aba permanece aberta. O gráfico da previsão segue a mesma verificação por fonte/variável dos indicadores; vencimento de rajada, por exemplo, não retira chuva válida ou observações históricas. Falta de dados não é normalidade.

## Leitura e consulta

A paleta neutra/verde e os temas existentes foram preservados. Eixos e unidades dos renderizadores compartilhados usam 13 px; legendas e leituras usam 14 px. Texto comum é verificado com contraste de 4,5:1 e séries essenciais com 3:1. A consulta não depende exclusivamente da cor.

O cursor informa valor, unidade, estação/modelo e término/intervalo. As setas, Home e End exploram leituras; Enter ou espaço fixa a consulta e Escape a libera. A vista por estação também aceita setas verticais. Movimento de ponteiro não gera anúncios contínuos; consultas por teclado usam uma região de status. No celular, a leitura aparece no fluxo abaixo do desenho, evitando encobrir as séries.

“Ver dados deste gráfico” oferece uma alternativa textual aos desenhos, respeitando o recorte. A tabela de previsão contém os horários originais antes do agrupamento. As tabelas são criadas ao abrir e paginadas em 50 registros; filtros e períodos novos reiniciam a paginação. Essa consulta usa os dados já carregados, sem chamadas adicionais aos provedores.

Os extremos e endpoints são preservados ao simplificar linhas densas. As lacunas são segmentadas antes da simplificação; todos os registros permanecem na consulta e na tabela. Os gráficos temporais de chuva deixam de criar dois elementos para cada janela móvel sobreposta.

## Arquivos e verificações

- `web/chart-utils.js`: escalas, eixos, identidade visual, intervalos previstos, lacunas, simplificação, consulta e tabela.
- `web/chart-interaction.js`: cursor, leitura fixa, teclado, toque e categoria vertical.
- `web/dashboard.js`: seleção das séries locais e previsões, estado e composição dos dois painéis.
- `web/app.js` e `web/forecasts.js`: adaptadores dos gráficos de previsão detalhada e comparação de modelos.
- `web/essential.css` e `web/home.css`: tipografia, tabelas e alinhamento responsivo das áreas de desenho por subgrid, sem espaçador de altura fixa.

Testes específicos: `node tests/chart_utils.cjs` e `python tests/ui_chart_improvements.py`. Integram os workflows existentes. Os cenários incluem 320, 390, 768, 1024 e 1440 px, ambos os temas, 4.800 observações sintéticas, zeros, horas ausentes, agrupamentos completos/parciais, paginação, identidade após filtro, teclado/fixação e vencimento individual. A suíte de layout existente também cobre 1920 px. Os dados sintéticos são interceptados apenas nos testes e nunca publicados.

Os testes não certificam usabilidade com pessoas nem equivalência científica entre fontes. Uma avaliação com usuários e leitor de tela real continua sendo uma validação complementar.

## Resultado da verificação local

Foram aprovados 449 testes Python, oito suítes JavaScript e as oito suítes de navegador (painel, detalhes, estação IFC, modelos, painel essencial, multifontes, atualização e novos gráficos). O build sintético e a validação dos produtos também passaram. O navegador local usado foi Chromium 158; o CI conserva sua versão isolada e verifica o PR novamente.

No ensaio sintético com 4.800 observações, janela de sete dias, viewport de 1440 px e sete redesenhos após aquecimento:

| Medida | Antes (main 4e93a50) | Depois |
| --- | --- | --- |
| Elementos SVG no gráfico observado | 19.222 | 46 |
| Mediana do redesenho completo dos painéis | 558,4 ms | 22,9 ms |
| Registros originais carregados | 4.800 | 4.800 |

A medição descreve esse ambiente e conjunto sintético; não é promessa de desempenho em todo dispositivo nem mede a velocidade das APIs meteorológicas. As verificações de extremos, lacunas e imutabilidade complementam a contagem de elementos.

## Operação e reversão

O pipeline meteorológico, a retenção e os contratos JSON permanecem iguais. O novo módulo é carregado antes dos consumidores nas duas páginas, e as referências de versão de CSS/JS foram atualizadas em conjunto. Reverter o PR restaura a apresentação anterior, sem migração ou reclassificação de dados.
