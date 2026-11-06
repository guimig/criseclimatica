# Cemaden PED — autenticação SGAA e consulta de chuva observada

## 1. Cadastro privado no GitHub Actions

No repositório [guimig/criseclimatica](https://github.com/guimig/criseclimatica), abrir **Settings → Secrets and variables → Actions → New repository secret** e criar:

| Nome do segredo | Valor inserido pelo mantenedor |
|---|---|
| `CEMADEN_PED_EMAIL` | E-mail utilizado no cadastro pessoal da PED |
| `CEMADEN_PED_PASSWORD` | Senha do cadastro PED |

**Não usar Repository variables.** Não colocar credenciais em código, arquivos públicos, issues, chat, logs, documentos ou configuração do navegador. Só o titular deve inserir os valores diretamente na interface do GitHub.

O fluxo anterior de `CEMADEN_PED_TOKEN` permanece como compatibilidade temporária, mas o JWT estático não deve ser necessário após a configuração completa dos dois Secrets. Em caso de apenas um segredo configurado, o sistema não tenta usar um token antigo potencialmente vencido.

## 2. Fluxo SGAA → PED no servidor

- O workflow Python consulta `POST https://sgaa.cemaden.gov.br/SGAA/rest/controle-token/tokens`, com JSON contendo `email` e `password` provenientes de **Secrets**.
- O SGAA retorna `token` e `timeToExp`. O manual de agosto de 2026 menciona JWT com validade de quatro horas. O Swagger atual descreve `timeToExp` em milissegundos, mas o manual também o chama de segundos em outra seção. **Não dependemos dessa unidade divergente**: é solicitado um JWT a cada execução e só há renovação se a PED sinalizar expiração (400/401).
- Em `GET https://sws.cemaden.gov.br/PED/rest/pcds-acum/acumulados-recentes?codibge=4201307&formato=JSON`, o JWT vai no **cabeçalho `token`**. Nunca é colocado em URL.
- Para não saturar a PED, as consultas autenticadas dos sete municípios são executadas sequencialmente. Em condições normais são sete GETs + uma autenticação por execução agendada (a cada três horas). A PED informa **limite de 12 requisições/minuto** para usuários externos; mais de uma execução simultânea deve ser evitada.
- Token não é persistido: só é mantido na memória do processo do GitHub Actions. O código bloqueia redirecionamentos automáticos e não imprime credenciais ou tokens.

## 3. Dados disponíveis

Os acumulados são referentes a **cada estação**, nunca à precipitação média do município. A API documenta janelas de **1, 3, 6, 12, 24, 48, 72, 96 e 120 horas**: os campos `rain_1h_mm`, `rain_3h_mm`, etc. são publicados no JSON `data/cemaden.json`. Janelas sobrepostas **não devem ser somadas**. Registros sem medição, com código IBGE diferente ou com horário inválido são descartados ou identificados como indisponíveis.

A página de instruções do portal exige a atribuição **“DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC”**. O JSON público contém esse identificador, e a aplicação apresenta a origem dos dados.

## 4. Implantação e teste

1. Faça o merge do pull request após o CI verde.
2. Cadastre `CEMADEN_PED_EMAIL` e `CEMADEN_PED_PASSWORD` nos **Repository secrets**.
3. Em **Actions**, execute manualmente `Update forecast and publish Pages`.
4. Confira o resumo nos logs: `Provider status: ... cemaden=available`, `no_recent_data`, `access_restricted`, `unavailable` ou `not_configured`. **Não habilite debug com `set -x` nem imprima o ambiente**.
5. Verifique `https://guimig.github.io/criseclimatica/data/cemaden.json`. O conteúdo deve ter apenas fonte, estado, municípios, estações, horários e acumulados. **Não pode conter e-mail, senha ou JWT**.
6. Se retornar `access_restricted`, confira a habilitação da sua conta aos webservices SGAA/SWS, sem compartilhar a senha. Se retornar `no_recent_data`, significa que a consulta não localizou dados recentes válidos, não que choveu 0 mm.

O teste automatizado usa **somente credenciais fictícias e respostas simuladas**. A autenticação com a conta real deve ser comprovada pelo usuário após inserir seus Secrets no GitHub.

## 5. Documentação oficial e fontes adicionais

- [Portal da Plataforma de Entrega de Dados](https://ped.cemaden.gov.br/home)
- [Catálogo SGAA](https://sgaa.cemaden.gov.br/SGAA/api/ui/) e [esquema JSON](https://sgaa.cemaden.gov.br/SGAA/api/ui/swagger.json)
- [Catálogo PED/SWS](https://sws.cemaden.gov.br/PED/api/ui/) e [esquema JSON](https://sws.cemaden.gov.br/PED/api/ui/swagger.json)
- Manual da PED anexado pelo usuário, agosto de 2026, páginas 3–9 e 32–33; FAQ da interface PED também anexada.
- O serviço permite consultas a cadastro de estações, dados recentes de sensores e agendamento de dados históricos. **Não foram habilitadas novas consultas históricas ou armazenamento externo nesta revisão**, preservando o escopo acordado.

**Segurança adicional:** como a conta cadastrada é pessoal, prefira uma senha exclusiva para a PED e revise quem possui acesso de escrita e aprovação de workflows no GitHub. Um Secret de repositório não impede que código malicioso inserido em um workflow autorizado tente utilizá-lo; revisar alterações da branch `main` continua necessário.
