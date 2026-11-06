# Integrações e integridade regional — etapa V9

## Por que a estação mais próxima pode não ter chuva medida?

No ZIP anual do INMET (atualizado com atraso), uma estação pode registrar uma linha para cada hora mas **não conter valor válido na coluna da precipitação**. Na publicação de 06/11/2026, o registro de Itapoá (A851) tinha 0/24 leituras válidas de chuva em cada um dos 14 dias exibidos. Os registros de Itajaí (A868), mais distantes de Araquari, tinham dias com 24/24 leituras. Não se conclui que choveu zero em Itapoá, nem que a chuva medida em Itajaí represente Araquari.

`regional_quality.py` seleciona, para cada ponto de amostragem, **a estação mais próxima dentre aquelas que possuem pelo menos um dia completo** de chuva no recorte fornecido pelo ZIP. Preserva no JSON a estação próxima sem dados, tornando a lacuna visível. Se não existir uma estação válida, publica `no_complete_gauge_data`. Um acumulado de sete dias só é calculado quando os sete dias consecutivos têm todas as 24 leituras. Dados antigos não se tornam "chuva recente".

A NASA POWER é uma **estimativa espacial em grade** de um ponto de Araquari. Quando houver valor da NASA e medição do INMET para o mesmo **dia UTC**, apresenta-se o par apenas para contextualizar duas fontes distintas; a comparação de pontos geográficos diferentes **não mede viés, acurácia nem erro do modelo**. A distância da estação é sempre mostrada.

* Arquivos: `src/observatorio/regional_quality.py`, `data/regional_quality.json`.
* Testes: `tests/test_regional_quality.py`.
* Fonte INMET: https://portal.inmet.gov.br/dadoshistoricos.

## Nova fonte: boletins editoriais Epagri/Ciram

Além dos avisos específicos, o portal Epagri/Ciram publica periodicamente boletins editoriais de **previsão de cinco dias** e **tendência de dez dias**:

* Categoria oficial: https://ciram.epagri.sc.gov.br/index.php/category/previsao/
* RSS: https://ciram.epagri.sc.gov.br/index.php/category/previsao/feed/
* Previsão municipal como consulta adicional: https://ciram.epagri.sc.gov.br/index.php/previsao-municipio-15-dias/

O adaptador `epagri_bulletins.py` lê até quatro publicações com até sete dias, valida origem HTTPS, data e XML; não executa scripts de HTML e não armazena dados sensíveis. Resumo e título são derivados do texto editorial, sem extrair números de mapas ou criar dados de estação. O conteúdo tem âmbito regional/estadual, não constitui aviso ativo emitido pela Defesa Civil nem previsão instrumental precisa de um município. Perdas de conexão têm estado `unavailable`, com preservação claramente assinalada de publicações anteriores por no máximo 24 horas.

* Arquivo: `data/epagri_bulletins.json`.
* Testes: `tests/test_epagri_bulletins.py`.
* A checagem de conectividade do PR é informativa; indisponibilidade remota não se confunde com CI de código.

## Epagri: dados ambientais medidos dos últimos 24 meses

A Epagri/Ciram informa disponibilizar gratuitamente, **mediante cadastro inicial e aceite das condições de uso**, planilhas de dados horários de sua rede, que são atualizadas mensalmente. Não existe nesta versão um fluxo de login ou automação autorizado e verificado para essa plataforma. O painel apresenta apenas um link seguro e direto para o serviço: https://ciram.epagri.sc.gov.br/dadosambientaispublicos/index.jsp. **Não coletar credenciais pessoais e não automatizar o login ou contornar restrições.**

## Escopo preservado

Os demais conectores, históricos compactos e estrutura GitHub Pages permanecem sem alteração. Nenhum Google Drive, banco pago, credencial nova, robô de login ou ampliação de retenção histórica foi introduzido. O fluxo de publicação gera JSON estático e continua protegendo a produção contra fixtures.
