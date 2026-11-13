import { useEffect, useState } from "react";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Relógio para os contadores. Atualiza 10x por segundo (os dígitos finais "correm"); quem
 * prefere menos movimento recebe uma atualização por segundo.
 */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = prefersReducedMotion() ? 1000 : 100;
    const id = window.setInterval(() => setNow(Date.now()), interval);
    return () => window.clearInterval(id);
  }, []);
  return now;
}
