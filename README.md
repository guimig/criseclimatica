# Observatorio do Tempo e Clima

Projeto aberto de monitoramento meteorologico, com foco em Araquari e no Litoral Norte de Santa Catarina. O MVP e um **portal estatico** publicado por GitHub Pages, atualizado por Python em GitHub Actions, sem banco pago nem Google Sheets.

> **Aviso:** os indicadores principais continuam sendo **estimativas e previsões da Open-Meteo**. A nova versão consulta avisos do INMET e boletins METAR de aeródromos próximos em módulos **separados**. Essas informações dependem de disponibilidade e podem estar atrasadas. Para risco e emergências, consulte diretamente a Defesa Civil e o INMET.

## Arquitetura inicial

- `src/observatorio/`: adaptadores, normalizacao, validacao, consolidacao e armazenamento local portavel.
- `config/locations.json`: sete coordenadas aproximadas usadas para amostragem do modelo. **Nao representam o limite municipal**.
- `scripts/build_site.py`: consulta Open-Meteo, prepara histórico de publicações, inventaria estações INMET, consulta avisos oficiais e boletins METAR e gera `dist/`.
- `web/`: frontend HTML/CSS/JavaScript sem backend de navegador.
- `tests/`: testes automatizados offline, com respostas ficticias.
- `.github/workflows/ci.yml`: testes em pushes e pull requests.
- `.github/workflows/pages.yml`: consulta real e publicacao a cada tres horas, com disparo manual.
- `docs/`: arquitetura, fontes, roadmap, retenção e política de integração.

Nenhuma credencial e enviada ao navegador; o provedor inicial nao exige token para uso nao comercial. O processamento e executado no servidor temporario do GitHub Actions, e os arquivos JSON resultantes sao publicados estaticamente. Quando uma fonte falha por completo, a compilacao falha e a implantacao anterior nao deve ser substituida.

## Rodar localmente

Requer Python 3.11+; Node.js e usado apenas para checagem opcional de sintaxe do frontend.

```bash
python -m unittest discover -s tests -v
python -m compileall -q src scripts
node --check web/app.js
python scripts/build_site.py --output dist
python -m http.server 8000 --directory dist
```

Abra `http://localhost:8000`. O comando de coleta real exige conexao HTTPS e disponibilidade da API Open-Meteo.

Para compilar sem acesso a internet, usando **dados sinteticos exclusivamente para testes**:

```bash
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --stations-fixture tests/fixtures/inmet_catalog.json --output dist
python scripts/validate_site.py --output dist --fixture
```

O site com `fixture_mode` nunca deve ser publicado: o navegador recusa o conjunto sinalizado como teste.

## Publicar no GitHub Pages

1. Integre o PR inicial a branch `main` depois dos testes.
2. Acesse **Settings > Pages > Build and deployment > Source: GitHub Actions**.
3. Em **Actions**, execute manualmente `Update forecast and publish Pages` para verificar a primeira coleta real.
4. Verifique logs, status da implantacao e a URL resultante, normalmente `https://guimig.github.io/criseclimatica/`.
5. O workflow tentara atualizar a previsao a cada tres horas (cron em UTC; os disparos podem atrasar ou ser omitidos).

O Pages nao executa Python quando alguem abre o site. O Python roda apenas durante os workflows. As consultas no navegador usam os JSONs publicados.

## Chuva observada e arquivo de avisos

A versão seguinte acrescenta consulta **opcional** à precipitação medida em estações INMET, sem confundir dados brutos de estação com estimativas Open-Meteo. A consulta depende de token autorizado e é desligada por padrão. Se o mantenedor obtiver uma credencial, pode armazená-la como *GitHub Actions repository secret* `INMET_API_TOKEN` (Settings → Secrets and variables → Actions). **Nunca** inclua credenciais no código, navegador, issues ou chat. Até que isso seja configurado e validado, a interface mostra que a integração pluviométrica não está habilitada.

Também é criado um arquivo progressivo `data/notice_history.json`, que preserva avisos anteriormente publicados para os municípios da região, sem inferir que um evento ocorreu ou que um aviso desaparecido foi cancelado. A recuperação depende da publicação anterior do Pages e **não é backup independente**. Documentação: [Chuva e histórico de avisos](docs/CHUVA_E_HISTORICO_AVISOS.md).

## Armazenamento e historicos

A fase incremental publica um **histórico progressivo de um snapshot de modelo por dia e localidade, limitado aos últimos 366 dias**, recuperando o arquivo da publicação anterior no GitHub Pages. Isso **não é backup independente** e não representa uma série de observações meteorológicas. O código também mantém as primitivas JSONL.GZ locais; integração a armazenamento externo permanente ainda depende de credenciais e validação. Não são utilizados banco pago, Drive ou planilhas no fluxo padrão.

A fase seguinte contemplara retenção seletiva (arquivo recente, resumo horario/diario/mensal, eventos) com backend externo gratuito quando a conectividade e o armazenamento forem validados. Nao se pretende registrar snapshots a cada tres horas em commits, pois isso aumenta desnecessariamente o historico Git. Consulte [Arquitetura](docs/ARQUITETURA.md).

## Fontes e atribuicao

Dados numericos: [Open-Meteo](https://open-meteo.com/en/docs) (uso gratuito nao comercial, conforme os termos e requisitos de atribuicao vigentes). Integracoes futuras: INMET, Epagri/Ciram, Cemaden, ANA, Defesa Civil SC e fontes maritimas, sujeitas a termos de acesso, autenticacao e testes.

## Situacao atual

- [x] Contratos de dados, adaptador Open-Meteo e validacao.
- [x] Build estatico e frontend responsivo por municipio.
- [x] Testes automatizados e pipeline de publicacao.
- [x] Primitivas para arquivos JSONL.GZ.
- [x] Usuario confirmou publicação e funcionamento inicial do GitHub Pages.
- [x] Inventário de estações INMET próximas, usando apenas metadados oficiais (sem medidas).
- [x] Histórico progressivo de publicações do modelo (não séries observadas).
- [x] Integrar **avisos INMET por IBGE** e **boletins aeroportuários METAR** em módulos opcionais (não pluviômetros); validar execução real após merge.
- [x] Implementar adaptador opcional para precipitação horária medida INMET, condicionado a token e teste real; **não está validado em produção**.
- [x] Histórico progressivo de avisos oficiais com deduplicação e retenção configurável.
- [ ] Confirmar acesso e funcionamento da API de observações do INMET com credencial autorizada.
- [ ] Persistencia historica externa e retencao automatica completa.
- [ ] Dados hidrológicos, pluviômetros, mapas e comparação de modelos.

Para o detalhamento, consulte [Roadmap](docs/ROADMAP.md), [Fontes](docs/FONTES.md), [Histórico e estações](docs/HISTORICO_E_ESTACOES.md) e [Avisos e METAR](docs/AVISOS_E_METAR.md).

## Integrações adicionais e diagnóstico de fontes

O painel diferencia **previsão Open-Meteo**, **observações METAR/NOAA**,
**avisos INMET**, **pluviometria de estações INMET e Cemaden (quando autorizadas)**
e **estimativas diárias NASA POWER**. A NASA é uma fonte distinta, mas seus
valores em grade **não são medições de pluviômetro**.

O arquivo `data/rain_gauges.json` indica o motivo da ausência de chuva
instrumental (`not_configured`, `access_restricted`, `no_recent_data`, etc.).
Para habilitar o acesso autorizado, configurar os segredos `INMET_API_TOKEN`
e/ou `CEMADEN_PED_TOKEN` em GitHub **Settings > Secrets and variables > Actions**.
Apenas obtê-los não garante disponibilidade da API. Não existe nenhuma
credencial embutida no repositório ou no site. O arquivo
`data/nasa_power.json` não precisa de segredo e é consultado no máximo uma vez
por dia quando a publicação anterior estiver íntegra.

Os serviços de coleta são **independentes**: se NASA/Cemaden/INMET falharem,
Open-Meteo continua publicando, com estados verificáveis. Os arquivos gerados
são os próprios dados efêmeros do Pages; **o armazenamento histórico não foi
ampliado nesta etapa**, conforme decisão de projeto.

Consulte [Integrações e chuva observada](docs/INTEGRACOES_FASE_ATUAL.md) para
fluxo de diagnóstico, limites e instruções de validação real.
