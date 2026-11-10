import type { ReactNode } from "react";
import type { Indicator, Status } from "../api/types";

function Notice({ title, children, role }: { title: string; children: ReactNode; role?: "alert" | "status" }) {
  return (
    <div role={role} className="border-l-[3px] border-link bg-surface px-5 py-4">
      <p className="font-semibold text-ink">{title}</p>
      <div className="mt-1 text-sm text-ink-2 prose-measure">{children}</div>
    </div>
  );
}

const Code = ({ children }: { children: ReactNode }) => (
  <code className="rounded bg-grid px-1.5 py-0.5 text-[0.85em] text-ink">{children}</code>
);

interface Props {
  apiDown: boolean;
  status: Status | undefined;
  indicators: Indicator[];
}

/** Avisos sobre o estado dos dados: API fora do ar, banco vazio, dados de demonstração, coletas falhas. */
export function Notices({ apiDown, status, indicators }: Props) {
  if (apiDown) {
    return (
      <div className="mt-6">
      <Notice title="Não foi possível falar com a API" role="alert">
        <p>
          O backend não respondeu. Em desenvolvimento, inicie-o com <Code>cd backend &amp;&amp; uvicorn app.main:app --reload</Code> e
          recarregue esta página.
        </p>
      </Notice>
      </div>
    );
  }
  if (!status) return null;

  const demo = indicators.filter((i) => i.is_demo).map((i) => i.name);
  const latestRunByCollector = new Map<string, Status["last_runs"][number]>();
  for (const run of status.last_runs) if (!latestRunByCollector.has(run.collector)) latestRunByCollector.set(run.collector, run);
  const failed = [...latestRunByCollector.values()].filter((r) => r.status === "error").map((r) => r.collector);

  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-2">
      {status.observations === 0 && (
        <Notice title="Ainda não há dados" role="status">
          <p>
            O banco está vazio. Rode <Code>python -m app.cli collect</Code> no backend para baixar os dados das fontes (ou
            ative <Code>WDV_BOOTSTRAP_ON_START=true</Code> para coletar sozinho na primeira inicialização).
          </p>
        </Notice>
      )}
      {demo.length > 0 && (
        <Notice title="Alguns números são de demonstração" role="status">
          <p>
            {demo.join(", ")} usam dados sintéticos, que <strong className="font-semibold">não são reais</strong>. Rode{" "}
            <Code>python -m app.cli collect</Code> para trocá-los pelos dados das fontes.
          </p>
        </Notice>
      )}
      {failed.length > 0 && (
        <Notice title="Uma fonte falhou na última coleta" role="status">
          <p>
            Sem resposta de: {failed.join(", ")}. Os dados dessa fonte podem estar desatualizados ou ausentes. Veja os
            detalhes em <Code>python -m app.cli status</Code> e tente de novo mais tarde.
          </p>
        </Notice>
      )}
    </div>
  );
}
