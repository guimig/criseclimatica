# Painel essencial — implementação

A composição aprovada na simulação passa a utilizar os dados publicados e as interações reais da aplicação. O retrato congelado, as datas, valores de exemplo e os textos promocionais da simulação não são incorporados. O título da inicial é **Tempo em Araquari**, sob a marca independente **Observatório · Tempo e Clima**. A página detalhada usa o mesmo cabeçalho, cores, tipografia e controles.

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

O nome correto da integração continua **Open-Meteo**, distinto de OpenWeather. Os coletores e os dados meteorológicos não são alterados neste trabalho. Os horários exibidos continuam em Brasília; as bases e janelas seguem as definições existentes. Referências vencidas continuam identificadas.

## Compatibilidade e validação

O tema claro/escuro e a preferência persistida são preservados. Os recursos de apresentação recebem uma referência de versão no HTML para evitar a combinação com estilos/scripts antigos em cache.

A validação inclui os testes Python e JavaScript existentes, geração/validação do site e navegador real nas duas páginas. Os testes de UX cobrem 320, 390, 768 e 1440 px, ambos os temas, links diretos, teclado, fontes, filtros, seleção de município, modelos e fixação/liberação da leitura por toque/clique.

Reversão: reverter o PR restaura a apresentação anterior sem migração, perda de históricos ou alteração de classificação. Não há credenciais novas ou consultas externas adicionais.
