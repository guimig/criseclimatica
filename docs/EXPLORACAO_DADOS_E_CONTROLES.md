# Controles, destaque da situação e exploração dos dados

## Página inicial

A cor da leitura atual aparece no destaque do título, na borda e no selo textual. O amarelo técnico é identificado como referência de atenção, preservando a distinção entre indício dos dados e nível institucional confirmado. A ausência de dados continua neutra. Nenhuma regra de enquadramento foi modificada.

Os gráficos de observações e previsão ficam sempre visíveis. O seletor de período aparece diretamente, sem bloco recolhível nem escolha dos gráficos visíveis. Cada gráfico mantém sua variável independente. Os filtros de área, estação e acumulado permanecem junto às observações. Em telas largas, as áreas de desenho compartilham as linhas da grade, sem espaçadores fixos na previsão. Em telas menores, os painéis ficam empilhados. Nomes de município em letras maiúsculas não repetem Araquari desnecessariamente nas legendas.

## Página de dados

A página mantém seus dados e os 99 identificadores anteriores, organizados em seis assuntos: Visão geral, Medições, Previsões, Avisos, Histórico e redes, Fontes. O município selecionado permanece visível fora dos assuntos; a síntese principal continua referente a Araquari.

A navegação usa uma seção por vez, com estado selecionado, setas/Home/End e histórico do navegador. Links anteriores, como `dados.html#cemaden-title` e `#archive-title`, selecionam o assunto e abrem os detalhes necessários. Cadastros, acumulados adicionais, séries históricas e fontes complementares ficam em blocos expansíveis, sem exclusão de informações. Com JavaScript indisponível, os blocos continuam presentes no documento.

A chuva Cemaden mostra nome, localidade e código secundário. Os acumulados de 1 h, 3 h e 24 h ficam em destaque; 6 h, 12 h e 48–120 h permanecem disponíveis no detalhamento de cada estação. Os valores originais, validações de atualidade e tratamento de falhas são preservados. O gráfico detalhado Open-Meteo permite consultar horários e valores por ponteiro, toque e teclado.

O visual acompanha a página inicial, com fundos neutros, verdes como acento, temas claro/escuro e textos legíveis. Fontes externas de tipografia deixam de ser necessárias. A troca de assunto não cria consultas meteorológicas adicionais nem altera o município silenciosamente.

## Verificação e reversão

Testes de navegação em Chromium cobrem os dois temas, 1440 e 390 px, abas, links diretos, histórico do navegador, troca de município, acumulados adicionais e interação do gráfico. Testes existentes continuam cobrindo dados vencidos e indisponíveis. Capturas sintéticas são guardadas pelo workflow de UX. Para reverter a apresentação, basta reverter o PR; não há migração de dados nem de históricos.
