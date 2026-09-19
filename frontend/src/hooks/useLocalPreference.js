import { useState } from 'react';

export function useLocalPreference(key, fallback) {
  const [value,setValue] = useState(() => {
    try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
  });
  function update(next) {
    setValue(previous => {
      const resolved = typeof next === 'function' ? next(previous) : next;
      try { localStorage.setItem(key,JSON.stringify(resolved)); } catch { /* Private browsing may disable storage. */ }
      return resolved;
    });
  }
  return [value,update];
}
