"use client";
import { useEffect, useState } from "react";

/** Load once on mount. `fetcher` returns openapi-fetch's { data, error }. */
export function useApi<T>(fetcher: () => Promise<{ data?: T; error?: unknown }>) {
  const [state, set] = useState<{ data?: T; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    fetcher()
      .then(({ data, error }) => set({ data, loading: false, error: error ? "Couldn't load" : undefined }))
      .catch(() => set({ loading: false, error: "Offline" }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}
