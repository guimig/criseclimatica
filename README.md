# Observatorio do Tempo e Clima

Projeto aberto de monitoramento meteorologico, com foco em Araquari e no Litoral Norte de Santa Catarina. O MVP e um **portal estatico** publicado por GitHub Pages, atualizado por Python em GitHub Actions, sem banco pago nem Google Sheets.

> **Aviso:** a primeira versao mostra **estimativas e previsoes numericas da Open-Meteo**, e nao leituras de estacoes meteorologicas. Nao existe ainda integracao automatica com alertas oficiais. Para risco e emergencias, consulte a Defesa Civil e os avisos do INMET.

## Arquitetura inicial

- `src/observatorio/`: adaptadores, normalizacao, validacao, consolidacao e armazenamento local portavel.
- `config/locations.json`: sete coordenadas aproximadas usadas para amostragem do modelo. **Nao representam o limite municipal**.
- `scripts/build_site.py`: consulta Open-Meteo e gera `dist/` para publicacao.
- `web/`: frontend HTML/CSS/JavaScript sem backend de navegador.
- `tests/`: testes automatizados offline, com respostas ficticias.
- `.github/workflows/ci.yml`: testes em pushes e pull requests.
- `.github/workflows/pages.yml`: consulta real e publicacao a cada tres horas, com disparo manual.
- `docs/`: arquitetura, fontes e roadmap de integracao.

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
python scripts/build_site.py --fixture tests/fixtures/open_meteo.json --output dist
```

O site com `fixture_mode` nunca deve ser publicado: o navegador recusa o conjunto sinalizado como teste.

## Publicar no GitHub Pages

1. Integre o PR inicial a branch `main` depois dos testes.
2. Acesse **Settings > Pages > Build and deployment > Source: GitHub Actions**.
3. Em **Actions**, execute manualmente `Update forecast and publish Pages` para verificar a primeira coleta real.
4. Verifique logs, status da implantacao e a URL resultante, normalmente `https://guimig.github.io/criseclimatica/`.
5. O workflow tentara atualizar a previsao a cada tres horas (cron em UTC; os disparos podem atrasar ou ser omitidos).

O Pages nao executa Python quando alguem abre o site. O Python roda apenas durante os workflows. As consultas no navegador usam os JSONs publicados.

## Armazenamento e historicos

A entrega inicial **nao usa banco, Drive ou planilhas**. Gera snapshots JSON pequenos para o site e inclui primitivas testadas para gravar e recuperar JSONL.GZ no disco, sem persistencia historica automatica entre workflows. GitHub Pages tambem nao constitui um repositorio historico permanente.

A fase seguinte contemplara retenção seletiva (arquivo recente, resumo horario/diario/mensal, eventos) com backend externo gratuito quando a conectividade e o armazenamento forem validados. Nao se pretende registrar snapshots a cada tres horas em commits, pois isso aumenta desnecessariamente o historico Git. Consulte [Arquitetura](docs/ARQUITETURA.md).

## Fontes e atribuicao

Dados numericos: [Open-Meteo](https://open-meteo.com/en/docs) (uso gratuito nao comercial, conforme os termos e requisitos de atribuicao vigentes). Integracoes futuras: INMET, Epagri/Ciram, Cemaden, ANA, Defesa Civil SC e fontes maritimas, sujeitas a termos de acesso, autenticacao e testes.

## Situacao atual

- [x] Contratos de dados, adaptador Open-Meteo e validacao.
- [x] Build estatico e frontend responsivo por municipio.
- [x] Testes automatizados e pipeline de publicacao.
- [x] Primitivas para arquivos JSONL.GZ.
- [ ] Validar execucao real da API no GitHub Actions e publicar Pages.
- [ ] Integrar observacoes instrumentais e alertas oficiais.
- [ ] Persistencia historica externa e retencao automatica completa.
- [ ] Dados hidrologicos, estações, mapas e comparacao de modelos.

Para o detalhamento, consulte [Roadmap](docs/ROADMAP.md) e [Fontes](docs/FONTES.md).
