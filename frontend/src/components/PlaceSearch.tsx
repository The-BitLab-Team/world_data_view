import { useEffect, useId, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Country } from "../api/types";
import { KIND_LABELS, mergeHits, placeName, searchLocal, type PlaceHit } from "../lib/places";

interface Props {
  /** Texto lido por leitores de tela (a caixa não mostra rótulo visível). */
  label: string;
  placeholder: string;
  countries: Country[];
  onSelect: (hit: PlaceHit) => void;
  /** Lugares que não devem aparecer (já escolhidos). */
  exclude?: string[];
  disabled?: boolean;
  className?: string;
}

const DEBOUNCE_MS = 250;

/**
 * Busca de lugares (mundo, continentes, países, estados e cidades). Países e continentes respondem na
 * hora, no navegador; estados e cidades vêm do servidor. Segue o padrão ARIA "combobox com lista".
 */
export function PlaceSearch({ label, placeholder, countries, onSelect, exclude = [], disabled, className = "" }: Props) {
  const uid = useId();
  const listId = `${uid}-lista`;
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [remote, setRemote] = useState<PlaceHit[]>([]);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  const query = text.trim();
  const excluded = useMemo(() => new Set(exclude), [exclude]);

  useEffect(() => {
    if (query.length < 2) {
      setRemote([]);
      setPending(false);
      setFailed(false);
      return;
    }
    setPending(true);
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api
        .searchPlaces(query, { limit: 10 }, controller.signal)
        .then((result) => {
          setRemote(
            result.map((p) => ({
              id: p.id,
              name: p.name,
              kind: p.kind,
              context: p.country_id && p.country_id !== p.id ? placeName(p.country_id) : undefined,
            })),
          );
          setFailed(false);
          setPending(false);
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setRemote([]);
          setFailed(true);
          setPending(false);
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const hits = useMemo(
    () =>
      mergeHits(searchLocal(query, countries), remote.map((hit) => ({ ...hit, name: placeName(hit.id, hit.name) }))).filter(
        (hit) => !excluded.has(hit.id),
      ),
    [query, countries, remote, excluded],
  );

  useEffect(() => setActive(0), [hits.length, query]);

  // Fecha ao clicar fora.
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const choose = (hit: PlaceHit) => {
    onSelect(hit);
    setText("");
    setRemote([]);
    setOpen(false);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (hits.length ? (i + 1) % hits.length : 0));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (hits.length ? (i - 1 + hits.length) % hits.length : 0));
    } else if (event.key === "Enter") {
      if (open && hits[active]) {
        event.preventDefault();
        choose(hits[active]);
      }
    } else if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        setOpen(false);
      } else {
        setText("");
      }
    }
  };

  const showList = open && query.length >= 2;
  const status =
    query.length < 2
      ? ""
      : hits.length > 0
        ? `${hits.length} ${hits.length === 1 ? "resultado" : "resultados"}`
        : pending
          ? "Buscando…"
          : failed
            ? "A busca de estados e cidades está indisponível."
            : "Nenhum lugar encontrado.";

  return (
    <div ref={root} className={`relative ${className}`}>
      <input
        type="search"
        role="combobox"
        aria-label={label}
        aria-expanded={showList}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={showList && hits[active] ? `${uid}-op-${active}` : undefined}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        placeholder={placeholder}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className="w-full rounded-md border border-hair bg-surface px-3 py-1.5 text-sm text-ink placeholder:text-ink-3 disabled:opacity-60"
      />
      <ul
        id={listId}
        role="listbox"
        aria-label={label}
        hidden={!showList || hits.length === 0}
        className="absolute left-0 z-40 mt-1 max-h-72 w-full min-w-64 overflow-auto rounded-md border border-hair bg-surface py-1 shadow-lg"
      >
        {hits.map((hit, index) => (
          <li
            key={hit.id}
            id={`${uid}-op-${index}`}
            role="option"
            aria-selected={index === active}
            // onMouseDown, não onClick: o campo perderia o foco antes do clique chegar.
            onMouseDown={(event) => {
              event.preventDefault();
              choose(hit);
            }}
            onMouseEnter={() => setActive(index)}
            className={`flex cursor-pointer items-baseline justify-between gap-3 px-3 py-1.5 text-sm ${
              index === active ? "bg-grid text-ink" : "text-ink-2"
            }`}
          >
            <span className="min-w-0 truncate">
              <span className="text-ink">{hit.name}</span>
              {hit.context && <span className="text-ink-3">, {hit.context}</span>}
            </span>
            <span className="shrink-0 text-xs text-ink-3">{KIND_LABELS[hit.kind]}</span>
          </li>
        ))}
      </ul>
      {showList && hits.length === 0 && status && (
        <p
          aria-hidden="true"
          className="absolute left-0 z-40 mt-1 w-full min-w-64 rounded-md border border-hair bg-surface px-3 py-2 text-sm text-ink-3 shadow-lg"
        >
          {status}
        </p>
      )}
      {/* Anuncia o estado da busca a quem usa leitor de tela, sem mexer no layout. */}
      <p role="status" className="sr-only">
        {showList ? status : ""}
      </p>
    </div>
  );
}
