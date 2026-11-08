"use client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { api, withUser, type Schemas } from "@/lib/api";

const UNDO_MS = 4000;
// Module-level so a delete still counting down survives switching tabs, and a refetch can't bring the row back.
const pendingDeletes = new Map<string, ReturnType<typeof setTimeout>>();

let basketLeft = 0;
const listeners = new Set<() => void>();
function publish(items: Schemas["ListItem"][] | undefined) {
  if (!items) return;
  const next = items.filter((i) => i.in_basket && !i.done).length;
  if (next === basketLeft) return;
  basketLeft = next;
  listeners.forEach((l) => l());
}
const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

/** Items in the Basket not yet ticked off, for the tab badge. */
export function useBasketCount() {
  useEffect(() => {
    api.GET("/items", { params: withUser() }).then(({ data }) => publish(data)).catch(() => {});
  }, []);
  return useSyncExternalStore(subscribe, () => basketLeft, () => 0);
}

/** Pantry state + mutations, shared by the list page and every intake sheet that saves into it. */
export function useItems() {
  const [items, setItems] = useState<Schemas["ListItem"][] | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [deleteError, setDeleteError] = useState<string | undefined>();

  useEffect(() => publish(items), [items]);

  const refetch = useCallback(() => {
    setLoading(true);
    return api
      .GET("/items", { params: withUser() })
      .then(({ data, error }) => {
        setItems(data?.filter((i) => !pendingDeletes.has(i.user_item_id)));
        setError(error ? "Couldn't load" : undefined);
      })
      .catch(() => setError("Offline"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  // A new postal code's flyers take about 30 s to download. Until they land every price here is blank, so wait for
  // them and reload once.
  useEffect(() => {
    let stop = false;
    (async () => {
      let waited = false;
      for (let tries = 0; tries < 40 && !stop; tries++) {
        const { data } = await api.GET("/flyers/status").catch(() => ({ data: undefined }));
        if (!data) return;
        if (data.ready) {
          if (waited && !stop) refetch();
          return;
        }
        waited = true;
        await new Promise((r) => setTimeout(r, 3000));
      }
    })();
    return () => {
      stop = true;
    };
  }, [refetch]);

  /** Throws on failure so callers (the intake flow) can keep their confirm sheet open and offer a retry. */
  const addItems = useCallback(async (body: Schemas["SaveItems"]) => {
    const { data, error } = await api.POST("/items", { params: withUser(), body });
    if (error || !data) throw new Error("save failed");
    setItems((prev) => [...data, ...(prev ?? [])]);
    return data;
  }, []);

  /** Hides the row now and deletes after the undo window. Returns the undo. */
  const deleteItem = useCallback((userItemId: string) => {
    setDeleteError(undefined);
    let restore: Schemas["ListItem"][] | undefined;
    setItems((prev) => {
      restore = prev;
      return prev?.filter((i) => i.user_item_id !== userItemId);
    });
    const timer = setTimeout(async () => {
      pendingDeletes.delete(userItemId);
      try {
        const { error } = await api.DELETE("/items/{user_item_id}", {
          params: { header: withUser().header, path: { user_item_id: userItemId } },
        });
        if (error) throw new Error("delete failed");
      } catch {
        setItems(restore);
        setDeleteError("Couldn't delete");
      }
    }, UNDO_MS);
    pendingDeletes.set(userItemId, timer);
    return () => {
      clearTimeout(timer);
      pendingDeletes.delete(userItemId);
      setItems(restore);
    };
  }, []);

  const patchFlags = useCallback(
    async (userItemId: string, flags: Pick<Schemas["ItemPatch"], "in_basket" | "done">, failure: string) => {
      setDeleteError(undefined);
      let previous: Schemas["ListItem"][] | undefined;
      setItems((prev) => {
        previous = prev;
        return prev?.map((i) => (i.user_item_id === userItemId ? { ...i, in_basket: flags.in_basket ?? i.in_basket, done: flags.in_basket === false ? false : flags.done ?? i.done } : i));
      });
      try {
        const { error } = await api.PATCH("/items/{user_item_id}", {
          params: { header: withUser().header, path: { user_item_id: userItemId } },
          body: flags,
        });
        if (error) throw new Error(failure);
      } catch {
        setItems(previous);
        setDeleteError(failure);
      }
    },
    [],
  );

  /** Moves a Pantry item into/out of the Basket. Optimistic, rolled back with deleteError's banner on failure. */
  const setBasket = useCallback(
    (userItemId: string, inBasket: boolean) =>
      patchFlags(userItemId, { in_basket: inBasket }, inBasket ? "Couldn't move to Basket" : "Couldn't remove from Basket"),
    [patchFlags],
  );

  const setDone = useCallback((userItemId: string, done: boolean) => patchFlags(userItemId, { done }, "Couldn't update that item"), [patchFlags]);

  /** Edits a Pantry item's identity. Throws on failure so the edit sheet can stay open and offer a retry. */
  const updateItem = useCallback(async (userItemId: string, fields: Schemas["ItemPatch"]) => {
    const { data, error } = await api.PATCH("/items/{user_item_id}", {
      params: { header: withUser().header, path: { user_item_id: userItemId } },
      body: fields,
    });
    if (error || !data) throw new Error("edit failed");
    setItems((prev) => prev?.map((i) => (i.user_item_id === userItemId ? data : i)));
    return data;
  }, []);

  return { items, loading, error, deleteError, addItems, deleteItem, setBasket, setDone, updateItem, refetch };
}
