# Integrações regionais: dez municípios e sensores recentes da PED/Cemaden

## 1. Cobertura geográfica

O Observatório mantém Araquari como localidade de referência e acompanha dez pontos urbanos aproximados em SC: Araquari, Joinville, Blumenau, Itajaí, Jaraguá do Sul, São Francisco do Sul, Itapoá, Garuva, Balneário Barra do Sul e Barra Velha.

As três novas localidades utilizam os códigos oficiais do IBGE:

| Município | Código IBGE | Latitude aproximada | Longitude aproximada |
| --- | --- | ---: | ---: |
| Blumenau | `4202404` | -26.9194 | -49.0661 |
| Itajaí | `4208203` | -26.9101 | -48.6705 |
| Jaraguá do Sul | `4208906` | -26.4851 | -49.0710 |

As coordenadas são **pontos de amostragem de modelo**, não limites municipais ou posição de instrumentos. O mesmo cadastro já é usado por Open-Meteo, CPTEC, avisos por IBGE e outros adaptadores; a disponibilidade é informada **por fonte** e por localidade.

## 2. Duas consultas independentes ao Cemaden

O atual `data/cemaden.json` continua usando a API de **acumulados recentes** por código IBGE, nas janelas de 1 a 120 horas. O novo `data/cemaden_sensors.json` utiliza outros recursos oficiais da PED/SWS:

- `GET /PED/rest/pcds/pcds-dados-recentes?rede=11&uf=SC&formato=JSON`: dados de sensores da rede 11 (Cemaden) nas **últimas três horas**. O pedido é regional para evitar um novo GET por município.
- `GET /PED/rest/pcds-tipo-estacao/sensores`: rótulos dos sensores por tipo de estação. Quando o catálogo não responde, o identificador do sensor é mostrado sem descrição inferida.

O endpoint responde com `codestacao`, `datahora`, `id_sensor`, `valor`, coordenadas e outras informações. Não presumimos que todas as estações tenham temperatura, vento ou vazão. **Os sensores efetivamente instalados e transmitindo determinam os campos disponíveis.** A exemplo da especificação PED, temperatura do ar e vazão podem aparecer; sem estação/sensor operacional, não há medição correspondente.

### Classificação e controle de qualidade

- Horário da observação em **UTC**, mostrado em horário local na interface; dados com mais de 3h20 não são classificados como recentes.
- Medição pontual com código da estação, nome, município informado pela fonte e distância em linha reta até o ponto escolhido. A seleção admite estações num raio de até 85 km e ordena por distância, sem atribuir a observação a toda a cidade.
- Um identificador de sensor é rotulado pelo catálogo, nunca por inferência de nomes não documentados. Unidades são apresentadas apenas quando confirmadas na especificação (ex.: temperatura do ar em °C, vazão em m³/s); outras aparecem sem unidade confirmada.
- Nulos, sentinelas numéricas e conflitos no mesmo sensor/instante são descartados; o código bruto de qualificação é preservado sem interpretação arbitrária.
- A lista traz no máximo seis estações próximas por localidade (cinco na primeira visualização). O conjunto do Estado retornado pela PED **não é publicado integralmente**.
- Um erro HTTP, ausência de estação, indisponibilidade de credencial ou excesso de dados nunca vira “0 mm”.
- Os JSONs publicados contêm somente informações meteorológicas públicas, sem JWT, e-mail ou senha.

## 3. Limite de requisições e atualização

A própria interface da PED informa **até 12 requisições/minuto para usuário externo**. Com dez consultas de chuva (uma por IBGE), mais uma consulta de sensores e outra ao catálogo, o projeto pode ultrapassar esse limite durante a execução.

Agora as duas integrações **compartilham a mesma sessão SGAA e um limitador conservador de 9 chamadas SWS a cada 61 segundos**. A primeira execução ampliada pode levar cerca de um minuto adicional; isso é esperado e evita bloqueios temporários. Requisições por expiração do JWT também passam pelo mesmo limitador. Não se cria um segundo usuário nem se aumenta a cadência de publicação.

**Não é monitoramento contínuo em tempo real.** O workflow atual executa aproximadamente de três em três horas, sem horário garantido pelo GitHub. Uma leitura recente significa apenas “recente no momento da coleta”, com horário de observação explícito. Alertas urgentes devem continuar vindo das autoridades competentes.

## 4. Impacto nos outros serviços

- **Open-Meteo:** mais três pontos de previsão de temperatura, precipitação, vento e rajadas, sempre identificados como produto de modelo.
- **CPTEC/INPE:** novas localidades entram no mesmo fluxo geográfico, sujeito à disponibilidade dos serviços.
- **INMET:** catálogos e outras fontes ganham cobertura dos novos pontos. O arquivo anual em cache agora recalcula as distâncias das estações ao receber novos municípios, sem baixar novamente o ZIP só por mudança da seleção geográfica.
- **Epagri/Ciram:** metadados de estações e publicações regionais continuam independentes das medições instrumentalmente confirmadas.
- **Cemaden:** agora são **dois produtos diferentes**, `cemaden.json` (acumulados por IBGE) e `cemaden_sensors.json` (sensores medidos por proximidade espacial).
- **NASA POWER:** segue com um ponto de referência em Araquari, para não criar consultas redundantes ao produto de grade diário.

## 5. Validação e implantação

1. Execute `python -m unittest discover -s tests -q`, `python -m compileall -q src scripts` e `node --check web/app.js`.
2. Gere o site com fixtures; `data/cemaden_sensors.json` deverá apresentar `fixture_mode` e **nenhuma leitura fictícia**.
3. Após integração do PR, execute `Update forecast and publish Pages` com `CEMADEN_PED_EMAIL` e `CEMADEN_PED_PASSWORD` previamente configurados como GitHub Actions Secrets. Não divulgue seus conteúdos.
4. Confira o estado `cemaden_sensors=...` no resumo sanitizado da execução; inspecione `data/cemaden_sensors.json` e o painel “Medições instrumentais recentes no entorno”.
5. Se a consulta regional do estado exceder o limite de tamanho aceito ou não tiver dados, o status será `unavailable` ou `no_recent_data`. Nesse caso, uma integração com recortes municipais ou paginação exigirá revisão separada de limites, sem publicação de respostas parciais como completas.

### Documentação e referências

- [Catálogo oficial PED/SWS](https://sws.cemaden.gov.br/PED/api/ui/) e [especificação JSON](https://sws.cemaden.gov.br/PED/api/ui/swagger.json)
- [SGAA](https://sgaa.cemaden.gov.br/SGAA/api/ui/) — autenticação JWT temporária
- [Códigos municipais IBGE](https://www.ibge.gov.br/explica/codigos-dos-municipios.php)
- Manual PED de agosto de 2026, seção 2.2, páginas 9–13 e seção 3.3, páginas 32–33; e FAQ de uso da plataforma enviado pelo usuário.

**Esta fase não cria cópia histórica independente, conta nova, banco de dados nem serviço pago.**
