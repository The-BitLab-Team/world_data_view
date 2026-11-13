import { useCallback, useState } from "react";
import { assignSlots } from "../lib/chartMath";
import { placeName } from "../lib/places";

export const MAX_ENTITIES = 4;
export const SLOT_COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];

export interface Comparison {
  entities: string[];
  /** Cor da entidade: segue o lugar, não a posição na lista. */
  colorOf: (id: string) => string;
  /** Nome em português para exibir (o nome da API só é usado para cidades e regiões). */
  nameOf: (id: string) => string;
  add: (id: string, apiName?: string) => void;
  remove: (id: string) => void;
  full: boolean;
}

/** Lugares escolhidos para comparar, com cor estável por lugar e no máximo MAX_ENTITIES. */
export function useComparison(initial: string[], initialNames: Record<string, string> = {}): Comparison {
  const [entities, setEntities] = useState<string[]>(initial);
  const [slots, setSlots] = useState<Record<string, number>>(() => assignSlots({}, initial, MAX_ENTITIES));
  const [names, setNames] = useState<Record<string, string>>(initialNames);

  const replace = useCallback((next: string[]) => {
    setEntities(next);
    setSlots((current) => assignSlots(current, next, MAX_ENTITIES));
  }, []);

  const add = useCallback(
    (id: string, apiName?: string) => {
      if (apiName) setNames((current) => (current[id] === apiName ? current : { ...current, [id]: apiName }));
      if (entities.includes(id) || entities.length >= MAX_ENTITIES) return;
      replace([...entities, id]);
    },
    [entities, replace],
  );

  const remove = useCallback(
    (id: string) => {
      if (entities.length > 1) replace(entities.filter((e) => e !== id));
    },
    [entities, replace],
  );

  const colorOf = useCallback((id: string) => SLOT_COLORS[slots[id] ?? 0], [slots]);
  const nameOf = useCallback((id: string) => placeName(id, names[id]), [names]);

  return { entities, colorOf, nameOf, add, remove, full: entities.length >= MAX_ENTITIES };
}
