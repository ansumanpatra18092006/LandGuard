import { useEffect, useRef, useState } from 'react';

export function toast(message) { window.dispatchEvent(new CustomEvent('landguard:toast',{detail:message})); }

const VISIBLE_MS = 4500;
const EXIT_MS = 300;

export default function Toasts() {
  // `message` is what the box holds; `visible` is whether it is on screen. They part ways for
  // one exit animation, so the toast slides out with its text rather than emptying first.
  const [message,setMessage] = useState('');
  const [visible,setVisible] = useState(false);
  const timers = useRef([]);

  function clear() { timers.current.forEach(clearTimeout); timers.current = []; }

  function dismiss() {
    clear();
    setVisible(false);
    timers.current.push(setTimeout(() => setMessage(''),EXIT_MS));
  }

  useEffect(() => {
    const show = event => {
      clear();
      setMessage(event.detail);
      setVisible(true);
      timers.current.push(setTimeout(() => {
        setVisible(false);
        timers.current.push(setTimeout(() => setMessage(''),EXIT_MS));
      },VISIBLE_MS));
    };
    window.addEventListener('landguard:toast',show);
    return () => { clear(); window.removeEventListener('landguard:toast',show); };
  },[]);

  return <div className={'toast' + (message ? ' is-present' : '') + (visible ? ' visible' : '')} role="status" aria-live="polite">
    {message && <><span>{message}</span><button className="ghost" aria-label="Dismiss notification" onClick={dismiss}>×</button></>}
  </div>;
}
