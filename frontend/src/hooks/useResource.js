import { useEffect, useRef, useState } from 'react';

// A single abortable request lifecycle for local REST resources; URLs own the filter state.
export function useResource(key, load, refresh = 0, delay = 180) {
  const loader = useRef(load);
  loader.current = load;
  const [version, setVersion] = useState(0);
  const [state, setState] = useState({ key: null, data: null, loading: true, error: '', updatedAt: null });
  useEffect(() => {
    const changed = () => setVersion(n => n + 1);
    window.addEventListener('landguard:data-changed', changed);
    return () => window.removeEventListener('landguard:data-changed', changed);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setState(previous => ({ key, data: previous.key === key ? previous.data : null, loading: true, error: '', updatedAt: previous.key === key ? previous.updatedAt : null }));
    const timer = setTimeout(() => {
      loader.current(controller.signal).then(data => {
        if (!controller.signal.aborted) setState({ key, data, loading: false, error: '', updatedAt: new Date() });
      }).catch(error => {
        if (!controller.signal.aborted) setState({ key, data: null, loading: false, error: error.message, updatedAt: null });
      });
    }, delay);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [key, refresh, version, delay]);
  return state.key === key ? state : { data: null, loading: true, error: '', updatedAt: null };
}
