import { useEffect, useState, type DependencyList } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  /** true enquanto uma requisição está em andamento (mesmo já havendo `data` anterior) */
  loading: boolean;
}

/**
 * Carrega dados assíncronos. Ao refazer a requisição (filtro mudou) mantém o `data` anterior,
 * para a interface esmaecer o conteúdo em vez de piscar um esqueleto e mudar o layout.
 */
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: undefined, error: undefined, loading: true });

  useEffect(() => {
    const controller = new AbortController();
    setState((previous) => ({ ...previous, error: undefined, loading: true }));
    load(controller.signal)
      .then((data) => setState({ data, error: undefined, loading: false }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState((previous) => ({
          data: previous.data,
          error: error instanceof Error ? error : new Error(String(error)),
          loading: false,
        }));
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
