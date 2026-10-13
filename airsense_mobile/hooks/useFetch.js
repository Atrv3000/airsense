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
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
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
