"use client";
import { useCallback, useEffect, useState } from "react";

/** Load on mount, with a `refetch` for a Retry button when `error` is set. `fetcher` returns openapi-fetch's { data, error }. */
export function useApi<T>(fetcher: () => Promise<{ data?: T; error?: unknown }>) {
  const [state, set] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });

  const refetch = useCallback(() => {
    set((s) => ({ ...s, loading: true }));
    fetcher()
      .then(({ data, error }) => set({ data, loading: false, error: error ? "Couldn't load" : undefined }))
      .catch(() => set({ loading: false, error: "Offline" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { ...state, refetch };
}
