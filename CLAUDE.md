# World Data View: guia para quem desenvolve aqui

Plataforma de dados globais: backend FastAPI + SQLite/PostgreSQL, frontend React + Vite. Documentação em português; código, identificadores e mensagens de commit seguem o que já existe no repositório (comentários e textos de interface em pt-BR).

## Comandos

```bash
# backend/  (venv: python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt)
python -m pytest -q                       # testes, sem rede
ruff check app tests                      # lint
python -m app.cli collect|seed-demo|status
python -m uvicorn app.main:app --reload   # :8000, docs em /docs

# frontend/
npm test && npm run typecheck && npm run build
npm run dev                               # :5173, proxy para :8000
```

Antes de entregar qualquer mudança: `pytest` + `ruff check` no backend e `npm test` + `npm run build` no frontend (o build já roda `tsc --noEmit`). O CI repete isso.

## Regras que não se negociam

1. **Honestidade dos dados.** Todo número tem fonte. Estimativa tem `kind="estimate"` e selo; dado sintético tem `source="DEMO"` (constante `DEMO_SOURCE` em `app/indicators.py`) e selo *demonstração*, inclusive em contadores e na curiosidade do dia. Nunca apresente dado de demonstração como real. Dado real de um indicador apaga as linhas `DEMO` dele (`drop_superseded_demo`).
2. **Contadores ao vivo são extrapolações.** O servidor devolve base e ritmo; o navegador calcula. Não troque isso por números inventados nem por polling por segundo.
3. **Coletores não derrubam nada.** `collect()` é puro e testável com cliente HTTP falso; `runner.py` captura falhas e registra em `collector_runs`. Uma fonte quebrada nunca pode impedir as outras nem a API.
4. **Um só eixo Y nos gráficos.** Para escalas diferentes, use o modo Índice 100, tabela ou gráficos separados. Cor segue a entidade (país/indicador), não a posição, e o texto nunca usa a cor da série.
5. **Todo gráfico tem tabela equivalente** e funciona por teclado; tooltip complementa, nunca é a única forma de ler um valor.

## Estrutura

- `backend/app/indicators.py`: catálogo de indicadores e categorias (fonte da verdade; a interface lê da API).
- `backend/app/collectors/`: um coletor por fonte + `runner.py` (persistência por *upsert*).
- `backend/app/services/`: `series`, `live`, `facts`, `demo`, `cache`.
- `backend/app/api/routes.py`: rotas `/api/v1`.
- `frontend/src/lib/`: funções puras (formatação pt-BR, escalas, normalização). É onde os testes do frontend vivem; mantenha a lógica aqui e os componentes finos.
- `docs/`: arquitetura, API e fontes de dados. Atualize junto com o código.

Para adicionar um indicador, veja o passo a passo em [docs/arquitetura.md](docs/arquitetura.md#como-adicionar-um-indicador).

## Armadilhas já encontradas

- **Listas na API são separadas por vírgula** (`country=BRA,USA`, `indicators=a,b`). Parâmetro repetido (`country=BRA&country=USA`) usa só o último valor.
- **Mundo = `WLD`**; países em ISO 3166-1 alfa-3.
- `co2_emissions` está em **milhões de toneladas**; `display.ts` converte para bilhões só no nível mundial. Por país, o mapa usa `mapFormat` (milhões), senão tudo vira "0,0".
- Nesta fonte tipográfica, vírgula e ponto *tabulares* ficam largos. Números com `tabular-nums` passam por `<Num>` para os separadores voltarem à largura normal.
- **`LineChart` mede o contêiner antes de desenhar o SVG.** Um SVG com largura inicial fixa estoura o grid no celular e a medição devolve o valor já inflado.
- Tailwind v4: tokens em `@theme inline` no `index.css`, tema por `data-theme` (claro/escuro, segue o sistema até a pessoa escolher).
- Este ambiente de desenvolvimento costuma não alcançar o Banco Mundial nem a NASA. Os coletores foram validados contra as fontes reais num runner do GitHub Actions (13/11/2026). Ao mexer neles, repita essa validação: uma branch descartável com um workflow que roda `python -m app.cli collect` e lê o resultado pelas anotações do *check run*.

## Revisão visual (interface)

Mudou layout ou gráfico? Olhe a tela, não só os testes: gere capturas em claro, escuro e 390 px de largura (por exemplo, `puppeteer-core` com o Chrome local e `page.emulateMediaFeatures` para o tema) e confira sobreposição de texto, estouro horizontal (`scrollWidth > clientWidth`), rótulos cortados, legendas e se o selo de demonstração/estimativa aparece onde deve. Teste também o fluxo de comparar países, Índice 100 e o tooltip.

## Commits

Mensagens curtas, no imperativo, descrevendo o *porquê*. Um assunto por commit.
