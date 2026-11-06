# Investigação e integração — catálogos INMET, CPTEC/INPE e Defesa Civil SC

Data de revisão: 05/11/2026. Esta entrega amplia fontes e não cria armazenamento externo.

## Os quatro endereços fornecidos

1. **[Catálogo de convencionais](https://portal.inmet.gov.br/paginas/catalogoman):** apresenta inventário oficial e opção de CSV. Para atualização automática de **metadados**, o aplicativo usa `https://apitempo.inmet.gov.br/estacoes/M`, com validação de código, coordenadas e nome. Não é uma fonte horária de medidas.
2. **[BDMEP](https://bdmep.inmet.gov.br/):** banco de dados meteorológicos com interface de consulta e exportação histórica, carregada em JavaScript. Não oferece, nos documentos verificados, API horária pública/estável para a aplicação. Não automatizar autenticação ou transpor mecanismos de proteção.
3. **[Catálogo de automáticas](https://portal.inmet.gov.br/paginas/catalogoaut):** usado como referência. O sistema já utilizava `https://apitempo.inmet.gov.br/estacoes/T` e agora combina as redes, indicando o tipo e preservando estações automáticas úteis para a pluviometria.
4. **[Tabela A001](https://tempo.inmet.gov.br/TabelaEstacoes/A001):** visualização de uma estação determinada. A página exige JavaScript. **A001 não é código de Araquari**; nunca derivar dados locais de um código de exemplo. Os cartões apresentam links com o código individual quando for automático.

Os metadados **não** asseguram que a estação reporte dados atuais. A distância é em linha reta, não uma equivalência meteorológica ou hidrológica. Quando os dados de observação automática estiverem inacessíveis, o painel de chuva observada continuará explicitando o problema, em vez de substituir observações por estimativas.

## CPTEC/INPE

Documentação: https://servicos.cptec.inpe.br/XML/

- Serviço de previsão de sete dias baseado em latitude/longitude, apontando a localidade geograficamente mais próxima.
- Não é medição instrumental nem necessariamente idêntico ao polígono do município selecionado.
- Condições, máximas, mínimas e UV são capturados do XML. Não são fabricadas quantidades de chuva; o XML documentado não disponibiliza acumulado numérico equivalente à Open-Meteo.
- HTTPS é exigido; se não estiver disponível, o sistema informa **indisponibilidade**, em vez de retroceder para HTTP não criptografado.
- Datas inválidas/antigas, outra UF, XML malformado e campos implausíveis são rejeitados.

## Defesa Civil de Santa Catarina

Fontes: https://www.defesacivil.sc.gov.br/boletins-do-tempo/ e https://www.defesacivil.sc.gov.br/alerta/

- O portal publica boletins para vários dias, avisos e alertas de curtíssimo prazo.
- Foi preparado coletor público via interface WordPress JSON (quando disponível), com tentativa de RSS oficial por categoria quando o portal não fornece publicações úteis.
- **Não é uma API de alertas com contrato de estabilidade confirmado.** O coletor poderá retornar `unavailable`, `partial` ou `no_recent_publications`.
- **Uma publicação intitulada ALERTA não é classificada automaticamente como alerta vigente.** A data de publicação não comprova validade, cancelamento ou risco atual. É exibida apenas como registro institucional, com link para o original.
- A identificação municipal depende de menção **explícita** no título/resumo, com normalização de acentos. Sem menção, não se declara que a localidade esteja segura ou excluída.
- Em situação de emergência, canais oficiais e avisos em tempo real são prioridade. Defesa Civil 199 e Bombeiros 193.

## Defesa Civil Araquari

Fonte municipal oficial: https://araquari.atende.net/subportal/secretaria-de-seguranca-publica-e-defesa-civil

O portal municipal não teve uma API aberta de alertas e previsões documentada e confirmada nesta revisão. Foi incluída referência institucional no painel, sem coletar notificações municipais de páginas não estruturadas. Alertas da Defesa Civil SC que mencionem Araquari podem aparecer entre as publicações identificadas, sem equivaler a aviso emitido pela prefeitura.

## Epagri/Ciram

Rede estadual: https://ciram.epagri.sc.gov.br/agroconnect/ e https://ciram.epagri.sc.gov.br/dadosambientaispublicos/index.jsp

Os serviços e o catálogo podem ter estações de interesse para Araquari e municípios próximos, mas uma API desassistida com uso autorizado não foi confirmada. Foram adicionados os links para consulta enquanto a integração é investigada.

## Validação e implantação

- Os contratos de todos os adaptadores são cobertos por testes offline; nenhum fixture pode ser publicado em produção.
- Executar `python -m unittest discover -s tests -v` e `python scripts/validate_site.py --output dist --fixture` após gerar `dist` com fixtures.
- Depois do merge, executar `Update forecast and publish Pages` e verificar estados em `data/stations.json`, `data/cptec.json` e `data/defesa_civil_sc.json` do site. Uma fonte `unavailable` requer investigação do serviço, não é evidência de ausência de risco.
- Bibliotecas: apenas biblioteca padrão Python. Nenhuma credencial nova, nenhum banco pago e nenhuma alteração no histórico persistente.
