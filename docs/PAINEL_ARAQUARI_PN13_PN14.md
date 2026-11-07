# Painel de acompanhamento de Araquari

## Referência vigente no aplicativo

As Portarias Normativas nº 13/2026 e nº 14/2026 — ASSINST/REI, de 04/11/2026, fornecidas pelo usuário, substituem integralmente o protocolo local anteriormente utilizado como referência do aplicativo. As cópias integrais estão em `web/references/pn-13-2026.pdf` e `web/references/pn-14-2026.pdf`, acessíveis pelo painel. A classificação anterior por eventos A/B/C/D deixou de ser emitida. A documentação histórica desse desenvolvimento não é regra ativa.

A PN 13 define seis categorias **qualitativas** (art. 6º), prioriza os avisos Epagri/Ciram (art. 4º), admite fontes complementares, especialmente Defesa Civil (art. 5º), e reserva as decisões sobre atividades à autoridade competente (art. 13). Não estabelece uma tabela numérica de precipitação, vento ou temperatura para converter valores em níveis.

Por isso, o painel distingue:

- **Nível sugerido para avaliação:** correspondência exploratória, produzida pelo aplicativo a partir de evidência prioritária explícita, com trecho usado, território, fonte e validade acessíveis.
- **Nível formal:** não é declarado pelo aplicativo. Não há ato decisório, cadastro administrativo nem registro de danos internos presumido.
- **Em avaliação:** faltam elementos suficientes para um enquadramento. Esse estado é neutro, sem cor verde automática.

## Método de enquadramento

Somente avisos Epagri/Ciram, em sua categoria própria, com consulta recente, URL oficial, região explícita incluindo Araquari/Litoral Norte e início/fim com fuso verificável podem sustentar uma sugestão. Boletim editorial, registro geográfico ou cor do INMET não substituem essa evidência. Referências regionais continuam identificadas como regionais, sem confirmação municipal de ocorrência.

As regras conservadoras estão em `src/observatorio/protocol.py`:

| Categoria | Tratamento no aplicativo |
| --- | --- |
| Verde / Normalidade | Não inferida da ausência de aviso, de valores baixos do modelo ou de fontes indisponíveis. Requer avaliação externa de normalidade |
| Azul / Preparação | Aviso prioritário com evento adverso explícito e janela começando em sete dias ou mais |
| Amarelo / Atenção | Aviso prioritário que menciona evento adverso e possíveis impactos pontuais, como alagamentos, destelhamentos ou interrupção de energia |
| Laranja / Alerta | Aviso prioritário com evento e expressão afirmativa de risco alto/elevado ou alta probabilidade. Correspondência exploratória, não equivalência oficial de escalas |
| Vermelho / Alerta Máximo | Aviso prioritário com evento e formulação explícita de perigo concreto, ameaça à vida ou tempestade severa iminente. Não decorre de pico numérico isolado |
| Roxo / Calamidade | Não inferido sem verificação de danos, duração do desastre ou decretos. Nenhuma notícia ou palavra isolada autoriza esse nível |

Expressões negadas não geram correspondência positiva. Quando vários avisos prioritários elegíveis sustentam categorias distintas, apresenta-se a de maior atenção sustentada, com todas as evidências; não se calcula a média de níveis. Não se combinam cores de órgãos diferentes em um escore.

Avisos complementares INMET permanecem visíveis nas evidências e são destacados na leitura principal quando retornados, mas não são convertidos diretamente nos seis níveis. A impossibilidade de conciliar seu fuso continua explícita.

### Cuidados normativos

A PN 13, art. 10, I, veda avaliações a partir do nível Laranja. A PN 14, art. 8º, III, sugere suspensão no Laranja e veda no Vermelho, remetendo à PN 13. O painel expõe essa divergência textual e não a resolve por código. Não automatiza orientações acadêmicas a partir dela.

A PN 14 disciplina a continuidade/reorganização acadêmica, não cria nova escala meteorológica. O painel disponibiliza as referências de até dez dias letivos e do prazo mínimo de uma semana para atividades, sem criar módulo de controle acadêmico. Os prazos de comunicação da PN 13 (22h do dia anterior / 12h / 17h) são referências informativas; situações emergenciais admitem comunicação a qualquer momento. Não há envio automático de mensagens.

## Tratamento dos dados

- **Araquari é o foco fixo.** Outros municípios permanecem na área complementar de dados.
- **Chuva observada:** estações da consulta pelo IBGE municipal; janelas de 24 h com horários de término a até 30 min da referência mais recente. A mediana só aparece com ao menos três estações. Mínimo, máximo, n, estações e horários ficam acessíveis. Não se representa essa distribuição como média de todo o município.
- **Pequenas amostras:** apresenta-se a maior leitura individual com identificação do número de estações. Dado zero é diferente de ausência. Duplicata idêntica não aumenta n; conflito no mesmo horário é excluído; uma leitura posterior da mesma estação substitui a anterior.
- **Chuva prevista:** total completo de 24 intervalos horários, maiores janelas consecutivas de 3/6 h e períodos explícitos. Não se soma previsão com observação nem acumulados sobrepostos.
- **Vento/rajada e temperatura:** máximos de 24 h condicionados à série completa. Referência descritiva de 30 °C não é limite normativo de calor nem sensação térmica.
- **Revisões:** publicação anterior e atual para as mesmas horas futuras e referência de grade; não é avaliação de desempenho do modelo.
- **Previsão:** consulta Open-Meteo ampliada para dez dias, preservando cotas de requisições e limites de normalização. Cada gráfico mostra o período efetivamente retornado.

Não se transforma NASA POWER, arquivo anual INMET ou histórico diário de publicações do modelo em medições recentes.

## Histórico observado

`data/observation_history.json` guarda somente observações pontuais de Araquari e referências instrumentais próximas identificadas, por até sete dias e no máximo 6.000 registros. Não é climatologia nem reconstrução retroativa. Há amostras de acumulados Cemaden e temperatura/vento/rajada METAR, e temperatura Cemaden com unidade documentada, quando retornadas.

As referências de temperatura/vento no histórico ficam a até 25 km do ponto municipal. Acumulados Cemaden usam a associação IBGE do coletor, sem inventar coordenadas de estações que não as forneceram.

O registro é consolidado por fonte, estação e horário. Valores conflitantes são retirados e a chave do conflito é preservada durante a retenção para tornar a reexecução idempotente. A mesma chave não reaparece como válida apenas por repetir uma publicação. Períodos ausentes não são interpolados. Linhas interrompem-se em lacunas maiores que quatro horas.

Após a primeira publicação, falha de recuperação ou desaparecimento desse arquivo impede a substituição do site, preservando a publicação anterior, como já ocorre com os demais históricos. A ausência de medições novas mantém as observações históricas com seus horários originais; nunca produz chuva zero ou melhora fictícia.

## Apresentação

A página inicial apresenta apenas o enquadramento, o aviso prioritário, quatro indicadores e um gráfico. As opções de chuva, vento/rajadas, temperatura, previsão/observações e período têm controles interativos, tooltip e exploração por teclado. Evidências, métodos e as seis categorias abrem em caixas de diálogo. A página `dados.html` conserva as fontes, estações, arquivos e municípios complementares, com retorno ao painel.

Não há logotipos oficiais ou afirmação de vínculo institucional. A inspiração cromática usa verde, branco e tons claros, com cores das categorias apenas como referência identificada. Fonte visual consultada: [paleta institucional publicada pelo IFFluminense](https://portal1.iff.edu.br/nossos-campi/reitoria/diretorias-sistemicas/diretoria-de-comunicacao/identidade-visual/elementos-secundarios). Adotam-se verde de acento `#2f9e41`, verde escuro `#23723b` para texto/contraste e fundo `#f5f8f4`; não se reproduz a composição gráfica da marca.

## Validade e verificações

`data/dashboard.json` mantém fonte, períodos, abrangência e método. A validade considera a publicação, os dados usados e o aviso prioritário; expiração retira enquadramento e indicadores atuais. Gráficos de publicações vencidas são identificados como referência anterior. Ao expirar, diálogos abertos também são fechados para não manter instruções com aparência atual.

A coleta permanece a cada três horas, sujeita a atrasos; o painel não é telemetria contínua. Atualizar a página consulta arquivos publicados, não as APIs em tempo real.

Comandos de verificação:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src scripts
node --check web/app.js
node --check web/dashboard.js
node tests/web_reliability.cjs
node tests/dashboard_behavior.cjs
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --output dist
python scripts/validate_site.py --fixture --output dist
```

Os testes cobrem validade, território, negadores, prioridade normativa, não conversão de cores, estatísticas de amostras pequenas, duplicatas/conflitos, continuidade, retenção e separação de séries. Fixtures seguem impedidas de publicação em produção.
