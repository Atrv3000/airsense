/**
 * useFetch — a simple reusable data-fetching hook.
 * Handles loading, error, and refresh states.
 * Usage: const { data, loading, error, refetch } = useFetch(url);
 */
import { useState, useEffect, useCallback } from 'react';

export function useFetch(url, options = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    if (!url) return;
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 12000);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timeoutId);
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error('Data endpoint not found (404). Check API configuration.');
        } else if (res.status === 429) {
          throw new Error('Rate limit exceeded (429). Please wait a moment.');
        } else if (res.status >= 500) {
          throw new Error(`Server temporarily unavailable (${res.status}). Service restarting.`);
        } else {
          throw new Error(`Request returned status ${res.status}`);
        }
      }
      const json = await res.json();
      setData(json);
    } catch (e) {
      if (e.name === 'AbortError') {
        setError('Request timed out. Please check your network connection.');
      } else {
        setError(e.message || 'Network request failed. Is the Django server running?');
      }
    } finally {
      clearTimeout(timeoutId);
      setLoading(false);
    }
  }, [url]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
