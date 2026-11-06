# Registro de decisoes de projeto

- Tecnologia definida: Python para ETL, GitHub Actions para agendamento e GitHub Pages para interface.
- Prioridade geografica: Araquari e Litoral Norte SC; visao Brasil por agregados numa fase posterior.
- Sem custo de banco de dados; nao utilizar Google Sheets como armazenamento principal.
- JSON pequeno para publicacao; JSONL.GZ para historicos e periodos encerrados, com persistencia remota a validar.
- Nao registrar dados atuais em commits Git a cada ciclo de coleta.
- Integracoes oficiais devem declarar restricoes de acesso e passar por testes antes de serem anunciadas no site.
- Manter historico regular dos dias normais e preservar detalhes selecionados de eventos; nao arquivar somente extremos.
- A fase 0 publica estimativas de modelo e nao afirma observacoes instrumentais ou alertas oficiais.
