# Leitura do painel, cores e cobertura das estações

## Problemas corrigidos

O resumo misturava atividade de monitoramento, faixas quantitativas auxiliares e níveis da PN 13/2026. Contadores como “superações” e “coincidências temporais” não explicavam o fenômeno. Com apenas uma coleta, o gráfico observado deixava quase toda a área vazia, com as três barras sobrepostas na borda. Códigos extensos e repetição do nome da fonte dificultavam reconhecer os locais.

## Situação em Araquari

As seis cores da PN 13/2026 são apresentadas com seus nomes: verde/Normalidade, azul/Preparação, amarelo/Atenção, laranja/Alerta, vermelho/Alerta máximo e roxo/Calamidade. O resumo usa texto e cor; não depende apenas da identificação de tonalidades.

São situações diferentes:

| Evidência disponível | Texto e cor no resumo | Significado |
| --- | --- | --- |
| Nível sustentado pelas regras vigentes | Nome do nível e sua cor | Sugestão consultiva; confirmar a competência e a decisão institucional |
| Estado de rotina, cobertura principal completa, sinais válidos existentes e todos abaixo das faixas | Normalidade nos dados acompanhados; referência verde | Descrição limitada às fontes monitoradas, especialmente chuva e vento; não é declaração oficial de nível verde |
| Valor em faixa auxiliar sem nível institucional sustentado | Atenção ao fenômeno; amarelo, sem marcar um nível específico na régua | Mostra valor, fonte, local e horário; não converte automaticamente uma faixa INMET em nível do IFC |
| Aviso regional ainda sem enquadramento | Há aviso meteorológico para conferir; amarelo, sem marcar nível específico | Ler abrangência e período nas evidências |
| Cobertura insuficiente ou validade vencida | Dados insuficientes / atualização necessária; neutro | Ausência de dados não é normalidade |

A regra consultiva e o histórico original não foram reclassificados. `suggested_level` e `official_level` não recebem verde a partir desta mudança visual. A fonte prioritária continua sendo Epagri/Ciram. Temperatura não recebe classe de risco sem critérios climatológicos. Não se concluem segurança, danos locais, funcionamento ou decreto a partir de ausência de aviso.

“Monitorar” é uma atividade realizada em qualquer nível. Por isso, deixa de ser o nome principal da situação atual. A explicação recolhida distingue valores acima de referência de contagem de eventos, e comparação temporal de confirmação ou precisão do modelo. Contadores técnicos saem do resumo inicial.

## Gráficos e identificação dos locais

- Mantêm-se os gráficos separados de observações e previsão, com leitura responsiva.
- Com menos de quatro horários distintos, a apresentação automática de chuva usa a última amostra de cada estação em barras horizontais, com nome e horário. Não cria amostras anteriores.
- “Ao longo do tempo” mantém as janelas efetivamente medidas, sem ligar os intervalos de chuva esparsos. A alternativa “Por estação” permanece disponível mesmo com histórico maior.
- A previsão usa barras horárias, preservando intervalos faltantes e a indicação da hora em curso.
- Os eixos usam passos arredondados. Gráficos temporais verticais compartilham escala apenas para acumulados compatíveis. A vista horizontal por estação e a previsão usam escalas próprias, explicitadas no texto; o gráfico por estação não possui eixo de tempo.
- No resumo e nas legendas, os nomes das localidades substituem códigos. A fonte comum aparece uma vez no cabeçalho. Códigos, coordenadas, distância e horários completos ficam no detalhamento.
- Nomes ausentes não são inventados: usa-se uma identificação de estação sem expor o código na visão inicial. O código original continua no detalhe.
- A informação ao passar o ponteiro desaparece quando o ponteiro deixa o gráfico. Navegação por teclado e toque continuam disponíveis.

## Por que aparecem três estações?

Não existe limite de três estações no produto de chuva de Araquari. A seleção local usa as estações retornadas pelo Cemaden para o IBGE municipal, com leituras recentes válidas. O número mostrado é o das estações com amostras disponíveis para a variável e o período selecionados, não um inventário de todas as estações instaladas no território. Chuva de 24 h no cartão continua preservando extremos e agrupando finais de janela com a tolerância temporal documentada.

A opção **Entorno · até 40 km** reaproveita leituras já coletadas de outros municípios. Só entram estações com posição conciliada por código e distância verificada de até 40 km do ponto municipal de Araquari. Não se presumem limites municipais, nem se chama todo o entorno de município limítrofe. Ausência de coordenadas é uma limitação explícita; não se usa distância do centro de outra cidade como distância da estação.

O entorno apresenta somente as últimas amostras disponíveis: não fabrica histórico regional, não se mistura à retenção local de sete dias, não altera a mediana de Araquari e não eleva o nível por votação de cidades. A lista é limitada a 24 estações próximas para manter a leitura utilizável. Nenhuma consulta externa nova é necessária.

## Navegação, fontes e validação

Links levam às fontes e à página de dados; botões identificados abrem explicações em diálogo; seções expansíveis guardam as tabelas. Os indicadores mostram sua ação de exploração, e uma legenda identifica Cemaden como observação e Open-Meteo como fonte das previsões de chuva, rajadas e temperatura.

A identidade mantém verdes como acento sobre superfícies neutras, texto legível e temas claro/escuro. As cores da norma ficam explícitas na situação e na régua. A página é independente e não utiliza logotipos oficiais.

Testes sem rede cobrem estados e validade, cores, nomes disponíveis e ausentes, gráficos esparsos, filtros, isolamento local/regional, coordenadas ausentes ou fora do raio e repetição. O workflow `Dashboard UX checks` executa Chromium com dados sintéticos interceptados somente durante o teste, nos tamanhos de 1440 e 390 px, e guarda capturas dos temas claro e escuro. Os dados de teste nunca são publicados no site. Playwright é instalado em ambiente isolado de CI, sem dependência adicional para quem usa o painel.
