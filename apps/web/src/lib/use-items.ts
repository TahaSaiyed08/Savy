"use client";
import { useCallback, useEffect, useState } from "react";
import { api, withUser, type Schemas } from "@/lib/api";

/** My List state + mutations, shared by the list page and every intake sheet that saves into it. */
export function useItems() {
  const [items, setItems] = useState<Schemas["ListItem"][] | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();
  const [deleteError, setDeleteError] = useState<string | undefined>();

  const refetch = useCallback(() => {
    setLoading(true);
    return api
      .GET("/items", { params: withUser() })
      .then(({ data, error }) => {
        setItems(data);
        setError(error ? "Couldn't load" : undefined);
      })
      .catch(() => setError("Offline"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  /** Throws on failure so callers (the intake flow) can keep their confirm sheet open and offer a retry. */
  const addItems = useCallback(async (body: Schemas["SaveItems"]) => {
    const { data, error } = await api.POST("/items", { params: withUser(), body });
    if (error || !data) throw new Error("save failed");
    setItems((prev) => [...data, ...(prev ?? [])]);
    return data;
  }, []);

  const deleteItem = useCallback(
    async (userItemId: string) => {
      setDeleteError(undefined);
      const previous = items;
      setItems((prev) => prev?.filter((i) => i.user_item_id !== userItemId));
      try {
        const { error } = await api.DELETE("/items/{user_item_id}", {
          params: { header: withUser().header, path: { user_item_id: userItemId } },
        });
        if (error) throw new Error("delete failed");
      } catch {
        setItems(previous);
        setDeleteError("Couldn't delete");
      }
    },
    [items],
  );

  return { items, loading, error, deleteError, addItems, deleteItem, refetch };
}
