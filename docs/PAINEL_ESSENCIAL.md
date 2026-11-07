# Painel essencial — implementação

A composição aprovada na simulação passa a utilizar os dados publicados e as interações reais da aplicação. O retrato congelado, as datas, valores de exemplo e os textos promocionais da simulação não são incorporados. A inicial usa apenas o título **Tempo em Araquari**, sem marca, logo ou chamada acima dele. A barra superior reúne os links Painel e Dados e fontes e o botão de tema em uma única linha, inclusive a 320 px. A página detalhada usa o mesmo cabeçalho, cores, tipografia e controles.

O tema claro combina fundo gelo acinzentado, superfícies suaves e verde como destaque. O escuro usa fundo grafite e superfícies neutras, com verde apenas nos detalhes. As cores dos seis níveis de risco mantêm os significados existentes.

## Organização

- Estado atual em uma faixa com a cor e o significado da referência. Os critérios, seis níveis e avisos prioritários ficam disponíveis por expansão ou explicação em diálogo. As regras de enquadramento e validade permanecem inalteradas.
- Indicadores essenciais em quatro colunas no desktop e duas no celular, com fonte, período e atalhos para os dados/gráficos.
- Observações e previsão permanecem separadas. Cada gráfico tem sua própria variável, para consultar rajadas previstas sem perder a chuva observada. O período comum, a escolha de um ou dois gráficos, os filtros por estação/entorno e a evolução observada continuam acessíveis em controles expansíveis.
- A chuva observada começa com acumulado explícito de 24 h, consistente com o indicador superior. A opção de 1 h permanece disponível. As barras de previsão continuam horárias; seus valores não são comparados diretamente com acumulados de 24 h.
- Comparação de modelos e memória de estados/avisos ficam recolhidas na abertura. Não há descarte de fontes, arquivos, períodos ou filtros. Os links e identificadores anteriores são preservados.
- A página de dados mantém os seis assuntos, consulta municipal e acumulados completos, com a mesma identidade visual da inicial. Araquari permanece a referência principal da síntese e da comparação de modelos.

## Gráficos

`chart-interaction.js` fornece o mesmo comportamento de consulta para o gráfico da inicial, o detalhado e a comparação entre modelos, sem biblioteca ou serviço novo:

- linha de consulta e marcadores dos valores correspondentes;
- leitura de horários, intervalos, unidades e fonte por mouse;
- clique/toque fixa a leitura; outro clique/toque ou Escape a libera;
- Home, End e setas permitem consultar por teclado;
- tooltip dimensionado e contido no painel para caber no celular;
- regiões sem amostra não viram zero nem são preenchidas por interpolação;
- eventos de ponteiro não disparam anúncios contínuos no leitor de tela; consultas por teclado têm anúncio próprio.

Cada SVG usa a largura disponível, com menos rótulos em telas estreitas. `ResizeObserver` refaz o desenho ao abrir uma aba antes oculta ou mudar a largura. A chuva detalhada passa a ocupar seu intervalo de uma hora, com eixo temporal real, em vez de posições equidistantes por índice. Linhas de temperatura/vento não unem lacunas horárias.

O nome correto da integração continua **Open-Meteo**, distinto de OpenWeather. Os coletores e os dados meteorológicos não são alterados neste trabalho. Os horários exibidos continuam em Brasília; as bases e janelas seguem as definições existentes. Referências vencidas continuam identificadas. No detalhamento, abrir uma aba ou redimensionar a tela não pode restaurar a previsão que foi retirada por desatualização.

## Compatibilidade e validação

O tema claro/escuro e a preferência persistida são preservados. Os recursos de apresentação recebem uma referência de versão no HTML para evitar a combinação com estilos/scripts antigos em cache.

A validação inclui os testes Python e JavaScript existentes, geração/validação do site e navegador real nas duas páginas. Os testes de UX cobrem 320, 390, 768 e 1440 px, ambos os temas, links diretos, teclado, fontes, filtros, seleção de município, modelos e fixação/liberação da leitura por toque/clique.

Reversão: reverter o PR restaura a apresentação anterior sem migração, perda de históricos ou alteração de classificação. Não há credenciais novas ou consultas externas adicionais.

## Padronização dos componentes

`web/essential.css` concentra os padrões compartilhados, organizados em seções legíveis: paleta, tipografia, navegação, ações, controles, expansões, painéis, indicadores, gráficos/tabelas, diálogos e responsividade. Os arquivos anteriores conservam os layouts específicos e as cores semânticas dos níveis de risco.

- Fundo claro `#edf2f0`, superfície `#f5f8f6` e superfície secundária `#e4ece7`: um passo mais escuros que a versão anterior. O escuro mantém a base grafite.
- Escala de espaçamento de 4, 8, 12, 16, 24 e 32 px. Painéis usam 24 px de recuo interno no computador e 16 px no celular; itens internos usam 12 ou 16 px conforme a densidade. Cantos de painéis com 8 px e controles com 6 px.
- Textos explicativos com 14 px, metadados com 13 px e rótulos com 12 px. A hierarquia de títulos distingue página, seção e painel; controles de seleção sobem para 16 px no celular para evitar zoom automático.
- Botões, filtros, links de ação e resumos expansíveis têm área de interação mínima de 44 × 44 px. Ações usam a mesma altura, fonte, borda, foco visível e estado de hover. Links no meio do texto mantêm a apresentação de link.
- As expansões usam o mesmo indicador à esquerda; conteúdo aberto recebe o mesmo recuo dos outros painéis. Painéis aninhados não duplicam bordas e cantos.
- Atualizar continua junto à referência de atualização nas duas páginas, inclusive no celular. Ações locais permanecem junto do respectivo conteúdo.
- Indicadores conservam a composição em faixas e os gráficos mantêm seus controles, fontes e separação entre medição e previsão.

Os testes de navegador verificam controles e expansões abertos/fechados nos seis assuntos da página detalhada, temas claro/escuro e larguras de 320, 390, 768 e 1440 px. Conferem contraste de texto dos controles de pelo menos 4,5:1, áreas de toque, ausência de rolagem horizontal da página e preservação das interações. Tabelas largas e a navegação por assuntos continuam com rolagem local. Diálogos também são conferidos com foco e fechamento por Escape.

## Atalho de chuva e descrições compactas

O indicador de chuva observada abre o gráfico da própria inicial, como os indicadores previstos: seleciona chuva, acumulado de 24 h, Araquari e todas as estações na visão por estação. Não navega para a página detalhada.

Na evolução temporal, acumulados móveis sobrepostos continuam desenhados com seus intervalos reais. O cursor mostra somente a leitura de cada série cujo fim do intervalo está mais próximo do horário consultado, entre os intervalos que contêm esse horário. O texto explicita o acumulado e o horário de referência de cada leitura; não soma, calcula média ou transforma o valor em chuva instantânea. Exibe no máximo quatro séries e informa quantas outras exigem filtro por estação. Marcadores acompanham somente as leituras descritas. O comportamento por teclado segue a mesma regra; sem amostra continua diferente de zero. Os registros, os títulos completos dos pontos e os filtros permanecem disponíveis.

A regressão inclui dezenas de faixas de 24 h por estação, consulta por mouse/toque/teclado, limite de tamanho do tooltip nos dois temas e navegação do indicador sem trocar de página.

## Leitura em computador

A partir de 1024 px de viewport, a coluna principal e a barra de navegação são centralizadas e limitadas a 960 px, com margens laterais de pelo menos 48 px. Os gráficos individuais e de comparação têm no máximo 720 px. Os dois gráficos da inicial continuam lado a lado no modo de comparação; ao exibir somente um, ele fica centralizado com largura limitada. A página detalhada mantém navegação lateral mais estreita e empilha os blocos de pluviômetros para evitar três cartões estreitos dentro da coluna. Textos explicativos ficam limitados a 72 caracteres de largura aproximada.

As regras são exclusivas do desktop. O layout abaixo de 1024 px, os controles de período/comparação, filtros e comportamentos dos gráficos permanecem os mesmos. A regressão inclui notebook de 1024 px e monitor de 1920 px, além das larguras já testadas.
