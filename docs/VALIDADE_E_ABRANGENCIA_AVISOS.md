# Vigência, fusos, abrangência e retenção de avisos oficiais

**Revisão:** 15/11/2026 · **Âmbito:** INMET e avisos meteorológicos Epagri/Ciram.

## Regra de autoridade temporal

**A vigência é definida pelo período oficial, não pela idade da coleta.** Um aviso
que termina às 23h permanece em vigor até o instante de término (limite
exclusivo), mesmo que o portal esteja sem comunicação há mais de seis horas.
A coleta ou a publicação do painel pode envelhecer; isso não equivale ao
encerramento do aviso. Apenas o término informado ou um cancelamento/revisão
efetivamente identificado na fonte altera seu estado.

- Horários com fuso explícito (UTC \`Z\`, \`-03:00\` ou outro deslocamento):
  respeitar o deslocamento informado.
- Data e hora sem fuso: interpretar em **America/Sao_Paulo**, horário civil de
  Brasília (UTC−3 para os períodos atuais).
- Datas sem hora: começar às 00h do primeiro dia e terminar às 00h do dia
  seguinte ao último dia incluído; a data final tem, portanto, suas 24h cobertas.
- Sem data de início ou fim identificáveis: não inventar janela. Exibir como
  **validade a confirmar** e encaminhar à conferência.
- Todo armazenamento dos instantes resolvidos continua em UTC; manter também
  texto e campos de origem. Um timestamp de publicação não substitui o período
  de risco.

### Exemplo prático

INMET: início 15/11/2026 às 08h, fim 15/11/2026 às 23h; sem fuso explícito.
Janela normalizada: \`2026-11-15T11:00:00Z\` até \`2026-11-16T02:00:00Z\`.
Consultado pela última vez às 09h, sem resposta nas consultas seguintes:
**continua vigente às 22h59**, mas sinaliza ausência de reconfirmação. Às
23h, expira. Não é evidência de que o fenômeno está ocorrendo em todo o período.

INMET apenas com dias 14 e 15/11: janela 14/11 00h até 16/11 00h,
com todo o dia 15 incluído.

## Fontes, versões e continuidade

- **INMET**: correspondência municipal por código IBGE de sete dígitos
  (Araquari: \`4201307\`). Coleta da API \`hoje\` e \`futuro\`;
  revisões com o mesmo identificador substituem versões anteriores.
  \`encerrado: true\` é cancelamento/encerramento explícito e impede retenção.
  Ausência de um identificador em resposta subsequente **não constitui**, por
  si, prova de cancelamento: registros anteriores com término no futuro são
  conservados e identificados como não reconfirmados.
- **Epagri/Ciram**: RSS dos avisos meteorológicos; recuperação pontual de
  páginas oficiais quando o RSS não apresenta janela explícita. Um registro
  previamente obtido com prazo futuro é conservado quando o RSS ou a fonte
  deixam de disponibilizá-lo; a indicação de atualização é independente.
  Epagri e Ciram constituem uma única fonte institucional.
- **Cancelamentos**: para INMET, o sinal \`encerrado\` é explícito. Uma
  publicação Epagri/Ciram nova com o mesmo URL substitui a anterior e seu
  período atualizado. Cancelamentos transmitidos por outro URL, sem referência
  estruturada ao aviso anterior, exigem conferência humana — o sistema não
  deduz cancelamento apenas da omissão do RSS.

Dados de coleta, observações instrumentais e modelos mantêm seus próprios
limites técnicos de atualidade, sem interferir no encerramento do aviso.


### Frequência de conferência Epagri/Ciram

O cache de avisos Epagri/Ciram foi reduzido para menos de 25 minutos, alinhado ao ciclo de geração de dados de aproximadamente 30 minutos. Assim, uma publicação nova ou um cancelamento não depende de um cache antigo de três horas. Essa política determina **quando verificar novamente** a fonte; nunca reduz o período oficial de vigência de um aviso já obtido.

## Reconhecimento do território de Araquari

A correspondência é dividida em três classes:

1. **Confirmada:** nome Araquari ou código IBGE exato; ou região identificável
   que inclua o município, como *Litoral Norte*, *Litoral catarinense*, *Norte
   catarinense*, *Região Metropolitana de Joinville*, *AMUNESC*, *Todo o estado*,
   *Todas* e *Todas as regiões*, respeitadas as exclusões.
2. **Possível — conferir:** expressões ambíguas, corpo do boletim com indicação
   local fora do campo de abrangência, mistura de inclusões/exclusões e
   descrições com regiões diferentes para dias diferentes.
3. **Não aplicável:** região exclusivamente distinta, município vizinho apenas
   nominalmente ou exclusão explícita de Araquari/Litoral Norte.

Exemplos: \`Todas, especialmente Litoral\` **inclui** Araquari;
\`Todas, exceto Litoral Norte\` **não inclui**; \`Planalto Norte\`
isoladamente **não** comprova abrangência; \`Litoral Norte na sexta-feira,
Oeste no sábado\` exige confirmação de período para o município e não deve
ser generalizado para ambos os dias.

A classificação do aplicativo continua **consultiva** e não substitui o
conteúdo do aviso ou a decisão da Direção-Geral. Avisos do entorno são
contexto regional, não comprovação de inclusão municipal. A detecção textual
não pode assegurar cobertura de todas as formulações futuras; exemplos
desconhecidos devem ser registrados para evolução do vocabulário.

## Fluxo técnico

1. \`notice_time.py\`: funções temporais comuns.
2. \`notice_territory.py\`: reconhecimento territorial conservador.
3. \`alerts.py\`, \`epagri_notices.py\`: normalização, revisão e preservação de
   avisos com término futuro.
4. \`analysis.py\`, \`protocol.py\`, \`multisource.py\`,
   \`risk_classification.py\`: extração e seleção com prazo oficial, sem
   restringir o aviso a seis horas desde a última consulta.
5. \`web/dashboard.js\`: apresentação dos avisos mesmo quando o painel de
   medições perdeu sua validade; a falta de atualização é informada, não
   convertida em ausência de risco.
6. \`notice_archive.py\`: histórico INMET; não confundir presença no arquivo com
   aviso atualmente aplicável ou desastre ocorrido.

## Operação, verificação e limitações

A publicação estática consome os avisos anteriormente publicados para
preservar a validade em falhas subsequentes. A retenção depende da
disponibilidade desse estado anterior. Sem uma primeira coleta bem-sucedida,
o sistema não tem como inventar avisos não observados. Falha de publicação
completa, perda do JSON anterior ou erro de build continuam exigindo
verificação no canal oficial.

### Testes obrigatórios

- Conferir datas e fuso com e sem deslocamento, datas sem horário e transição
  da meia-noite; conferir término exclusivo.
- Validar repetição, revisão e encerramento explícito INMET.
- Simular falha de consulta superior a seis horas, com aviso ainda válido.
- Simular ausência no feed mais recente sem encerramento expresso.
- Cobrir abrangência estadual, regional, município, exclusão e regiões distintas
  por dia; casos ambíguos devem impedir falsa afirmação de cobertura.
- Executar suíte Python e JS, build de fixture, \`validate_site.py\` e
  testes visuais em desktop/mobile antes de mesclar o PR.
- Conferir live fonte e site após publicação real; CI e fixtures não substituem
  a confirmação do funcionamento dos provedores.

**Reversão:** reverter o merge ou restaurar a última versão estável. Não
excluir o histórico de avisos ao reverter o código.