// useApi: fetch JSON from our API inside a React component.
//
//   const { data, error, loading } = useApi<Scout>(url);
//
// - Re-fetches whenever `url` changes (pass null to fetch nothing yet).
// - Cancels the previous request when the url changes or the component unmounts
//   (AbortController), so a slow old response can never overwrite a newer one.

import { useEffect, useState } from "react";
import { getJson } from "./api";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export function useApi<T>(url: string | null): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: null, error: null, loading: false });

  useEffect(() => {
    if (url === null) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const controller = new AbortController();
    setState((prev) => ({ data: prev.data, error: null, loading: true }));
    getJson<T>(url, controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return; // we cancelled it on purpose
        setState({ data: null, error: err instanceof Error ? err.message : String(err), loading: false });
      });
    return () => controller.abort(); // cleanup: runs before the next fetch and on unmount
  }, [url]);

  return state;
}
