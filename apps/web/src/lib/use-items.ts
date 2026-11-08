"use client";
import { useCallback, useEffect, useState } from "react";
import { api, withUser, type Schemas } from "@/lib/api";

/** My List state + mutations, shared by the list page and every intake sheet that saves into it. */
export function useItems() {
  const [items, setItems] = useState<Schemas["UserItem"][] | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | undefined>();

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

  const addItems = useCallback(async (body: Schemas["SaveItems"]) => {
    const { data } = await api.POST("/items", { params: withUser(), body });
    if (data) setItems((prev) => [...data, ...(prev ?? [])]);
    return data;
  }, []);

  const deleteItem = useCallback(async (userItemId: string) => {
    setItems((prev) => prev?.filter((i) => i.user_item_id !== userItemId));
    await api.DELETE("/items/{user_item_id}", {
      params: { header: withUser().header, path: { user_item_id: userItemId } },
    });
  }, []);

  return { items, loading, error, addItems, deleteItem, refetch };
}
