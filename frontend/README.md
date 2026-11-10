# Frontend

Painel do World Data View: React 19, TypeScript, Vite e Tailwind v4. Gráficos e mapa são SVG próprio sobre d3-scale, d3-shape e d3-geo.

```bash
npm install
npm run dev          # http://localhost:5173 — proxy de /api e /docs para http://localhost:8000
npm test             # testes das funções puras (formatação, escalas, normalização)
npm run typecheck    # tsc --noEmit
npm run build        # checagem de tipos + build de produção em dist/
```

Para apontar para outra API durante o desenvolvimento: `VITE_DEV_API_TARGET=http://host:porta npm run dev`.

Em produção o frontend é estático (`dist/`) e espera a API no mesmo domínio em `/api/v1` (por exemplo, atrás de um proxy reverso). Estrutura e decisões de visualização: [../docs/arquitetura.md](../docs/arquitetura.md#frontend-frontendsrc).
