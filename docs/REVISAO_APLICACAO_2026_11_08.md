# Revisão geral da aplicação — 08/11/2026

## Escopo e método

Revisão das camadas de configuração, adaptação de fontes, processamento temporal, síntese, classificação, retenção/recuperação de históricos, geração de artefatos, workflows, carregamento frontend, gráficos e documentação. A base foi a versão publicada após o PR 32. Foram inspecionados contratos entre camadas e os mecanismos de validação, além das regressões Python, JavaScript e navegação em navegador real.

Foram mantidos layout, páginas, URLs, municípios, fontes, credenciais, retenções, faixas de chuva/vento e prioridades normativas. Não foi introduzido framework, banco, serviço externo ou dependência de execução. As mudanças são localizadas nos limites onde dados ou publicações passam de uma camada para outra.

## Problemas comprovados e correções

| Área | Problema | Correção |
| --- | --- | --- |
| Geração local | A saída anterior era removida antes de instalar a nova pasta, sem restauração se a movimentação falhasse | Validação do diretório temporário antes da substituição; renomeação no mesmo sistema de arquivos e restauração em caso de falha |
| Caminho de saída | Uma configuração incorreta de `--output` podia apontar para fonte/ancestral do projeto | Rejeição antes de consultar provedores; proteção de `src`, `web`, `scripts`, `tests`, `docs`, `config`, `.github`, `.git`, raiz/ancestrais e links simbólicos |
| Artefato frontend | A lista manual de arquivos obrigatórios não cobria todas as dependências declaradas nos HTML | Validação dos `src`/`href` de scripts e links locais de `index.html` e `dados.html`, incluindo caminhos contidos no diretório publicado |
| Open-Meteo | Um horário com offset explícito recebia um `Z` adicional, produzindo uma referência inválida | Conversão de horários com offset para UTC; formatos UTC já aceitos preservados e datas sem horário rejeitadas |
| Rede Open-Meteo | Uma conexão interrompida por `ConnectionResetError` escapava do mecanismo de repetição existente | Mesmo limite de tentativas passa a cobrir esses erros de conexão; sem aumentar a quantidade configurada de tentativas |
| Arquivo municipal | O navegador podia combinar um resumo novo com um arquivo `places/{id}.json` anterior enquanto a CDN propagava | Correspondência do `collected_at`, até duas leituras, recusa de mistura de versões e de arquivo sintético |
| Falha de leitura municipal | Reabrir o mesmo município com a mesma publicação apagava a leitura em uma falha de rede | Preservação da leitura anterior apenas se município e publicação forem compatíveis; prazos continuam originais |
| Versão frontend | Um recarregamento manual podia aceitar publicação anterior retornada por uma borda CDN | Recusa de regressão de versão tanto na home como nos detalhes |
| Comparação de modelos | O comparador detalhado só carregava ao abrir a página e depois apenas vencia, mesmo com o restante atualizado | Consulta de novas versões pelo mesmo mecanismo de polling; variável e período escolhidos preservados |
| Dados de comparação | Estruturas malformadas podiam gerar exceção no renderizador | Validação da forma de janelas, métricas, séries e contexto CPTEC; falha limitada à comparação, preservando a anterior quando válida |

## Verificações preservadas

- Credenciais e tokens Cemaden ficam no processo Python, com login sem redirecionamento e repetição sincronizada; o navegador consulta somente arquivos públicos.
- Requisições, respostas e arquivos anuais têm limites próprios de tamanho; CSV de ZIP não é extraído para caminhos fornecidos pelo arquivo.
- Gravações JSON rejeitam valores não finitos e usam arquivo temporário. Históricos distinguem observação, previsão arquivada e aviso oficial.
- Fontes locais não são substituídas por municípios vizinhos. Proximidade de estação não prova representatividade ou precisão do modelo.
- Estados de falha, falta de dados, zero e referência vencida continuam distintos. Nenhuma correção transforma ausência de informação em normalidade.
- Conteúdo das fontes é inserido por nós de texto; links institucionais continuam sujeitos às restrições de origem existentes.
- Controles por toque/teclado, temas e disposições responsivas permanecem cobertos pelos testes de navegação.

## Validação

As regressões acrescentadas exercitam saída protegida, link simbólico, falha de renomeação com restauração, artefato inválido sem troca, reconstrução repetida, dependência HTML ausente, offsets UTC, interrupção transitória de conexão, divergência entre resumo e arquivo municipal, recusa de versão anterior, dados malformados de comparação e atualização automática do comparador mantendo seletores.

O workflow continua executando as suítes Python/JavaScript e a validação antes de publicar, além dos testes de navegador na revisão. O validador dentro do build é uma proteção adicional para execução local; a validação do workflow permanece.

## Revisão complementar: falhas parciais e prazos entre camadas

Uma carga parcialmente malsucedida podia já ter aceitado o `generated_at` novo no resumo. O polling passava a considerar a versão carregada e não repetia o arquivo faltante até outra publicação. A carga agora registra pendências e tenta repará-las mesmo na mesma versão, com o limite existente de uma tentativa por minuto e exclusão de concorrência. Uma leitura secundária anteriormente válida só é conservada dentro da mesma publicação; a origem e seus horários não são renovados. Se apenas o arquivo municipal falhou, a repetição é direcionada a ele. Corpo válido de fonte indisponível não representa erro de carregamento.

O resumo só é aceito após o conjunto de consultas secundárias terminar, com o identificador da requisição ainda atual. Publicações com data excessivamente futura são rejeitadas antes de substituir a versão carregada, impedindo que uma data incorreta bloqueie a recuperação posterior pelo controle contra regressão.

O comparador passa a limitar seu prazo pelas oito horas de validade de coleta/referência dos modelos utilizados, além do teto de três horas da publicação. Modelos indisponíveis são excluídos dessa redução. Faixas, prioridade e parâmetros meteorológicos permanecem iguais.

Regressões complementares cobrem reparo da mesma versão, preservação do Cemaden durante falha de leitura seguida de recuperação em navegador real, tentativa municipal pendente, data excessivamente futura e comparação com referência antiga/indisponível.

Um arquivo municipal sem os blocos `current`, `hourly` ou `daily` também é recusado antes de substituir a leitura. Se a renderização falhar sem cache compatível, o objeto inválido é retirado do estado, evitando que o temporizador tente renderizá-lo novamente e interrompa a atualização dos demais blocos.

## Limitações e operação

GitHub Actions continua sujeito a atraso/omissão de eventos. A indisponibilidade do coletor da Defesa Civil e o acesso opcional ao INMET observado não são resolvidos por mudanças de frontend. Esta revisão não demonstra precisão meteorológica local nem substitui avaliação institucional.

Use `--output` somente para uma pasta destinada ao site gerado: seu conteúdo anterior é substituído após validação. Proteções de caminho não transformam essa pasta em armazenamento de documentos pessoais. A recuperação local cobre falha na instalação do novo diretório; os arquivos publicados no Pages não são backup independente.

Uma reversão pode ser feita pelos commits desta revisão, sem migração de dados ou alteração de segredos. Ver [arquitetura atual](ARQUITETURA.md), [algoritmo](ALGORITMO_CLASSIFICACAO_NIVEIS.md) e [auditoria de confiabilidade](AUDITORIA_CONFIABILIDADE.md).
