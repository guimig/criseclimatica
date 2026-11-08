# Auditoria geral e continuidade — 08/11/2026

Revisão do código da aplicação em `88a38de`, preservando as funcionalidades em uso. Complementa a [revisão anterior](REVISAO_APLICACAO_2026_11_08.md) e a [auditoria de atualização](AUDITORIA_CONFIABILIDADE.md). Esta revisão não altera as regras meteorológicas ou a competência institucional para decidir níveis.

## Escopo e método

Foram examinados o fluxo de coleta Python, adaptadores e limites de validade, regras de classificação, históricos, construção/validação dos artefatos, workflows, carregamento e recuperação dos dados no navegador, gráficos, contratos da interface e documentação. A suíte completa de regressão foi executada; a interface é conferida também pelo CI em Chromium, com dados sintéticos interceptados apenas nos testes.

## Falhas verificadas e correções

| Área | Evidência no código anterior | Correção |
| --- | --- | --- |
| Consistência entre arquivos | `app.boot()` conferia o `generated_at` da síntese e o `collected_at` municipal, mas várias fontes secundárias eram aceitas apenas pelo tipo/esquema. Respostas de diferentes bordas do CDN poderiam misturar publicações ainda recentes. | Todos os JSON recebem `publication_at`, igual ao `generated_at` do manifesto. O frontend detalhado exige a identidade da publicação para fontes e arquivos municipais quando o manifesto usa o novo contrato. Componentes divergentes ficam pendentes e são buscados novamente. |
| Validação do build | O artefato possuía verificações individuais, sem identidade compartilhada entre todos os JSON. | O validador percorre os JSON, inclusive arquivos municipais, e rejeita identidade divergente antes de substituir a saída. |
| Recuperação da home | Falha isolada de `observation_history.json` resultava em histórico nulo, mas o polling não recarregava a mesma versão já aceita do dashboard. | `incompleteHistory` mantém a tentativa automática mesmo sem nova publicação. A última cópia verificada só é preservada quando pertence à mesma publicação. Um aviso informa a limitação sem suspender dados independentes. |
| Expiração com aba aberta | O temporizador atualizava a faixa principal, mas a legenda dos gráficos só era recalculada após interação ou nova carga. | A legenda é atualizada quando a publicação perde validade. O gráfico histórico permanece identificável como referência anterior. Evita-se reconstruir os gráficos a cada minuto sem mudança de validade. |

## Contrato de publicação e compatibilidade

`publication_at` identifica o **artefato**, não a coleta, emissão do modelo, vigência de aviso ou medição de estação. `retrieved_at`, `checked_at`, `collected_at`, referências e prazos individuais não são renovados por esse campo. Produtos obtidos de cache conservam seus relógios reais e suas limitações.

Manifestos antigos sem o campo permanecem compatíveis com o formato anterior. Manifestos novos exigem o campo correspondente nos componentes. Um componente com identidade divergente não substitui uma cópia verificada da mesma publicação; a recuperação continua marcada como pendente. Não se usa cópia antiga para preencher uma publicação nova. Reversão é possível pela reversão do commit; campos adicionais são ignorados pelas versões anteriores.

## Funcionalidades preservadas

- Home com painel essencial, dois gráficos e período visível; temas, responsividade e navegação mantidos.
- Avisos Epagri/Ciram e INMET na inicial apenas quando há evidências aplicáveis; consultas negativas permanecem em Dados e fontes.
- Prioridade normativa Epagri/Ciram; avisos INMET contextuais, sem participação no classificador.
- Critérios, faixas numéricas, estações, municípios, distâncias e prazos científicos mantidos.
- Credenciais exclusivamente no processo Python; não há chamadas autenticadas no navegador.
- Troca da saída validada e reversível, preservação dos arquivos históricos e recusa de fixtures em produção.

## Verificação

316 testes Python passaram, incluindo duas regressões adicionais para identidade dos arquivos e preservação dos horários reais. As quatro suítes JavaScript passaram; sintaxe e build/validação offline também foram aprovados. Os testes Chromium ampliados verificam histórico inicialmente inacessível, recuperação da mesma publicação, componente secundário de versão divergente, preservação de cache verificado e legenda vencida com aba offline aberta. Os resultados do CI do PR acompanham esta revisão.

A conferência de links internos Markdown não encontrou destinos inexistentes. Foram atualizadas a arquitetura, as orientações de operação e a descrição de recuperação. Esta auditoria não constitui prova de ausência de todos os erros nem certificação das fontes meteorológicas.

## Limitações externas

O Pages é estático. Um navegador recupera publicações já geradas; não dispara a coleta no Actions. Agendamentos podem atrasar ou ser omitidos, e fontes externas podem falhar ou exigir autorização. Os testes simulam indisponibilidade e inconsistências, mas não garantem disponibilidade permanente dos serviços, representatividade de estações ou atualização em tempo real. Nenhuma regra foi relaxada para transformar ausência ou dado vencido em normalidade.
