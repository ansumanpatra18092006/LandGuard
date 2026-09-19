import { useRef } from 'react';
import { X } from 'lucide-react';
import { useDialogTransition } from '../../hooks/useDialogTransition';

export default function Modal({ open, onClose, title, className = '', children }) {
  const { ref, phase } = useDialogTransition(open);
  const close = useRef(onClose);
  close.current = onClose;

  // Children stay mounted through the exit so the overlay animates out with its content
  // intact rather than emptying first and then sliding away.
  if (phase === 'closed' && !open) return <dialog ref={ref} className={'app-modal ' + className} aria-label={title}/>;

  return <dialog ref={ref} className={'app-modal ' + className} data-phase={phase} aria-label={title}
    onCancel={event => { event.preventDefault(); close.current(); }}
    onClick={event => {
      if (event.target === event.currentTarget) {
        const rect = event.currentTarget.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close.current();
      }
    }}>
    <div className="modal-heading"><h2>{title}</h2><button className="icon-button ghost" onClick={onClose} aria-label={'Close ' + title}><X size={20}/></button></div>{children}
  </dialog>;
}
