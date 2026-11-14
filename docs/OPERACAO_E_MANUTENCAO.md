# Operação, implantação e manutenção

**Referência técnica:** revisão de 14/11/2026, `main` no commit `3ec7bb9`. Este é um guia do comportamento do repositório, não prova de disponibilidade de cada provedor no instante da leitura.

## 1. Serviços e responsabilidades

| Camada | Local | Responsabilidade |
| --- | --- | --- |
| Configuração territorial | `config/locations.json` | 20 pontos amostrais de SC/PR; Araquari é a referência fixa |
| Coleta e cálculo | `src/observatorio/`, `scripts/build_site.py` | Consultar fontes, normalizar, sintetizar evidências, classificar e gerar JSON |
| Validação | `scripts/validate_site.py` | Verificar contratos, identidade da publicação e arquivos estáticos |
| Apresentação | `web/` | HTML/CSS/JS sem backend persistente, sem credenciais nem requisições autenticadas pelo navegador |
| CI | `.github/workflows/ci.yml` | Testes Python/JS, build sintético, validação e sondagem informativa |
| Publicação | `.github/workflows/pages.yml` | Coleta real, validação, artefato e deploy no Pages |
| UX | `.github/workflows/ui.yml` | Testes de navegador em PRs que alteram os caminhos indicados no workflow |
| Disparo principal externo | cron-job.org, fora do Git | Solicitar `workflow_dispatch` a cada 30 minutos; detalhes em [agendamento](ATUALIZACOES_30_MINUTOS.md) |

O GitHub Pages publica a última geração **bem-sucedida**. O campo `generated_at` ou `publication_at` não pode ser interpretado como horário de medição de todas as fontes. [Contratos de dados](CONTRATOS_DADOS_E_HISTORICOS.md).

## 2. Pré-requisitos e configuração

- Python **3.11+** (CI e deploy usam 3.12); Node.js para verificações JavaScript. `pyproject.toml` não declara dependências Python externas.
- GitHub Pages configurado para a origem **GitHub Actions**; branch padrão `main`.
- `CEMADEN_PED_EMAIL` e `CEMADEN_PED_PASSWORD` são secrets opcionais para autenticação SGAA; `CEMADEN_PED_TOKEN` é compatibilidade legada. `INMET_API_TOKEN` é opcional e depende de autorização real para observações recentes.
- O token do cron-job.org fica **exclusivamente no armazenamento privado do serviço externo**, restrito ao repositório e à permissão de disparar Actions. Não o copie para Markdown, issues, logs, JS, páginas ou URL.
- Não crie segundo agendamento primário antes de desabilitar o anterior. Token expirado ou secret faltante não significa necessariamente falha global: algumas fontes podem continuar disponíveis.

## 3. Validação local isolada, sem coleta real

Execute no diretório raiz:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src scripts
node --check web/app.js
node --check web/dashboard.js
node --check web/weather-synthesis.js
node tests/web_reliability.cjs
node tests/dashboard_behavior.cjs
node tests/dashboard_loading.cjs
node tests/campus_station.cjs
node tests/publication_refresh.cjs
node tests/forecast_contract.cjs
node tests/weather_synthesis.cjs
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --stations-fixture tests/fixtures/inmet_catalog.json --output dist
python scripts/validate_site.py --output dist --fixture
python -m http.server 8000 --directory dist
```

O modo fixture gera **dados sintéticos**, não acessa serviços autenticados e **não pode ser publicado como produção**. A validação `--fixture` é específica do ensaio. Em ambiente sem acesso ao repositório e suas dependências, o CI remoto é o lugar adequado para esses comandos; este documento não declara sua execução. Os testes Chromium estão em `tests/ui_*.py` e seu workflow próprio instala Playwright. Como `ui.yml` possui filtro de caminhos, **uma alteração apenas em `docs/` não aciona automaticamente os testes visuais**.

## 4. Ciclo de atualização

1. O cron-job.org envia `POST` autenticado ao endpoint de `pages.yml/dispatches`, com `{"ref":"main"}`, nos minutos **00 e 30**. `HTTP 204` confirma apenas o **aceite do disparo**.
2. `pages.yml` inicia também em `push` na `main` e manualmente. O agendamento GitHub `7,37 * * * *` é reserva.
3. O passo `scripts/check_refresh.py` força a coleta nos eventos diferentes de `schedule`. No `schedule`, compara a publicação acessível: idade **>=25 min**, data inválida, expiração ou falha de acesso obrigam coleta; versão validamente recente dispensa build e deploy.
4. Antes da coleta real, o job executa testes Python e contratos JS. Depois `scripts/build_site.py --output dist --previous-url https://guimig.github.io/criseclimatica/` lê os históricos anteriores, consulta fontes, monta produtos e executa uma primeira validação.
5. O script cria uma árvore temporária e faz substituição local por renomeação com restauração em caso de erro. O workflow valida os JSON novamente, envia artefato `github-pages-${{ github.run_attempt }}` e realiza o deploy.
6. O navegador verifica a existência de versão mais recente com a aba visível, em intervalos de cerca de um minuto. O botão atualizar **não** inicia um workflow.

A execução depende dos runners, de provedor meteorológico, de recuperação de históricos previamente publicados e do serviço Pages. Não há garantia de início e conclusão nos minutos do cron.

## 5. Rotina de verificação

Para cada incidente, anote: **horário UTC e horário de Brasília, ID da execução, evento (`workflow_dispatch`, `schedule` ou `push`), SHA da branch, status de build/deploy, `generated_at`, `publication_at`, `valid_until` e status da fonte relevante**.

1. Confira [execuções do workflow](https://github.com/guimig/criseclimatica/actions/workflows/pages.yml) e se houve um evento externo no último horário esperado.
2. Se houve `HTTP 204` mas nenhuma execução, confira repositório/ref, autenticação e registro da API; não conclua que houve deploy.
3. Se o workflow não iniciou, confira cron-job.org, validade do token, permissões e o agendamento de reserva. Nunca divulgue cabeçalhos privados ao registrar evidências.
4. Se iniciou mas falhou em **Validate code before collecting**, procure regressão de teste: a falha ocorre **antes** de consultar provedores.
5. Se falhou em **Fetch live forecast and build static site**, confira logs e distinguish: indisponibilidade de fonte; HTTP 429/5xx; histórico obrigatório perdido/inválido; classificação/contrato; ou falha no próprio processo. Um HTTP 503 na recuperação do Pages tem repetição limitada, não autoriza reinicializar histórico.
6. Se falhou em **Verify dataset integrity**, não publique o artefato sem validação. Investigue `publication_at`, produtos incompatíveis, datas e fixtures.
7. Se o build concluiu mas não houve deploy, confira **Upload site artifact**, o nome versionado por `run_attempt`, a etapa **Deploy to GitHub Pages** e eventual propagação.
8. Se o deploy concluiu, mas o usuário vê leitura antiga, compare diretamente `data/latest.json`, `data/dashboard.json`, identidade da publicação e relógio dos dados; o frontend pode recusar temporariamente combinações de CDN inconsistentes.
9. Se apenas uma fonte aparece indisponível, examine o respectivo JSON e seus horários. **Ausência de coleta não comprova ausência de aviso ou segurança meteorológica.** O coletor Defesa Civil SC tem limitação de rede comprovada no runner em 13/11; ver [diagnóstico](DEFESA_CIVIL_COLETA_QUALITATIVA.md).

Os históricos das falhas e investigações anteriores permanecem em `AUDITORIA_CONFIABILIDADE.md` e `RECUPERACAO_PUBLICACAO_2026_11_09.md`. Esses arquivos são registros datados, não a política de cron atual.

## 6. Continuidade, recuperação e reversão

- **Falha geral de provedores operacionais:** o build aborta e mantém a publicação anterior. Catálogos ou arquivo anual, sozinhos, não sustentam um painel renovado.
- **Fonte parcial:** pode haver publicação válida com status de fonte/variável parcial; não transforme indisponível em zero.
- **Histórico já marcado como publicado, mas ausente ou inválido:** o build recusa reconstruir um histórico vazio que apagaria a continuidade.
- **Retorno do Pages/CDN:** verifique novamente a publicação e seus arquivos antes de considerar um histórico perdido. Repetições são limitadas para evitar carga sem fim.
- **Rollback de documentação:** use `git revert` no commit do PR. Para código, nunca restaure versão antiga sem verificar compatibilidade dos contratos com os históricos atualmente publicados.
- **Recuperação de desastres:** os arquivos Pages são cópias públicas de conveniência, **não backups independentes**. Um mecanismo externo de backup/retenção exigirá decisão de arquitetura e testes próprios.

**Não faça:** forçar publicação de fixtures; remover histórico para “fazer o build passar”; expandir artificialmente validade; expor tokens; inventar alerta/nível; ou publicar dados sem a verificação do validador.

## 7. Checklist de manutenção após mudanças

- [ ] Código e testes correspondem ao comportamento documentado.
- [ ] Fonte, território, tipo de dado, referência temporal e validade descritos corretamente.
- [ ] Execução Python/JS e build fixture com validação completos; registrar falhas se houver.
- [ ] CI verde e, se houver mudança de interface, workflow de UX/inspeção visual conferidos.
- [ ] Em mudanças de dados, formato, histórico ou risco: verificar compatibilidade com o Pages existente e plano de rollback.
- [ ] Primeira coleta real pós-merge e seu deploy confirmados; os próximos ciclos observados, sem alegar estabilidade por um único êxito.
- [ ] README, [índice](INDICE.md), [contratos](CONTRATOS_DADOS_E_HISTORICOS.md) e [roadmap](ROADMAP.md) atualizados, quando aplicável.

O monitoramento meteorológico é consultivo e não automatiza suspensão de aulas ou decisões das autoridades.
