import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "wdv-theme";

function systemTheme(): Theme {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedTheme(): Theme | null {
  try {
    const value = window.localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null; // armazenamento indisponível (modo privado, iframe...)
  }
}

/** Segue o tema do sistema até a pessoa escolher um; a escolha fica salva neste navegador. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => storedTheme() ?? systemTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(KEY, next);
      } catch {
        /* sem persistência: vale só para esta visita */
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
