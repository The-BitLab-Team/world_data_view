import { useEffect, useState } from "react";
import { parseRoute, type Route } from "../lib/places";

/** Rota atual, lida do hash da URL (#/lugar/BRA-SC). Não depende de configuração do servidor. */
export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));

  useEffect(() => {
    const onChange = () => {
      const next = parseRoute(window.location.hash);
      setRoute((current) => {
        if (current.page === next.page && (current.page === "home" || (next.page === "place" && current.id === next.id))) {
          return current;
        }
        return next;
      });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  return route;
}
