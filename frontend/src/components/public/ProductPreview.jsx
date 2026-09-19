import { useState } from 'react';
import { ArrowRight, RotateCcw, X } from 'lucide-react';
import { Link } from 'react-router-dom';

// Public walkthrough fixtures only. Never fetch or expose workspace records here.
const examples = [
  {id:'EX-01',name:'Example road connector',district:'North district',approvals:3,compensation:42,possession:28},
  {id:'EX-02',name:'Example irrigation link',district:'South district',approvals:0,compensation:84,possession:70},
  {id:'EX-03',name:'Example rail extension',district:'North district',approvals:1,compensation:66,possession:51},
];
export const previewViews = ['Dashboard','Analytics','Projects'];
export default function ProductPreview({view,onView}) {
  const [pending,setPending] = useState(false);
  const [district,setDistrict] = useState('');
  const [selected,setSelected] = useState(null);
  const rows = examples.filter(p => (!pending || p.approvals > 0) && (!district || district === p.district));
  const active = rows.find(p => p.id === selected);
  function changeScope(action) { action(); setSelected(null); }
  function keyboard(event,index) {
    const next = {ArrowRight:(index+1)%3,ArrowLeft:(index+2)%3,Home:0,End:2}[event.key];
    if (next === undefined) return;
    event.preventDefault(); onView(previewViews[next]);
    document.getElementById('preview-tab-' + next)?.focus();
  }
  return <section className="product-preview" id="product-preview" aria-label="Interactive product walkthrough">
    <div className="preview-top"><span><i/> TRY THE WORKSPACE</span><span>Fictional examples</span></div>
    <div className="preview-tabs" role="tablist" aria-label="Preview views">{previewViews.map((name,i) => <button key={name} id={'preview-tab-'+i} role="tab" aria-selected={view === name} tabIndex={view === name ? 0 : -1} aria-controls="preview-panel" onClick={()=>onView(name)} onKeyDown={event=>keyboard(event,i)}>{name}</button>)}</div>
    <div className="preview-body" id="preview-panel" role="tabpanel" aria-labelledby={'preview-tab-'+previewViews.indexOf(view)}>
      <div className="preview-instruction" key={view}><h2>{view === 'Dashboard' ? 'Find the work needing attention.' : view === 'Analytics' ? 'Compare, then narrow your scope.' : 'Open the story behind a record.'}</h2><p>{view === 'Dashboard' ? 'Try the approvals card. The example queue responds.' : view === 'Analytics' ? 'Select a district bar to focus the example records.' : 'Select an example project to reveal its recorded progress.'}</p></div>
      {view === 'Dashboard' && <div className="preview-metrics"><div><span>In this scope</span><strong>{rows.length}</strong><small>example projects</small></div><button aria-label="Preview projects with pending approvals" aria-pressed={pending} onClick={()=>changeScope(()=>setPending(!pending))}><span>Pending approvals</span><strong>{rows.reduce((sum,p)=>sum+p.approvals,0)}</strong><small>{pending ? 'Selected · click to clear' : 'Click to filter'} <ArrowRight size={12}/></small></button></div>}
      {view === 'Analytics' && <div className="preview-comparison" aria-label="Example district comparison">{['North district','South district'].map(name => {
        const group = examples.filter(p=>p.district === name && (!pending || p.approvals>0));
        const average = group.length ? Math.round(group.reduce((sum,p)=>sum+p.compensation,0)/group.length) : null;
        return <button key={name} aria-label={'Preview '+name} aria-pressed={district === name} onClick={()=>changeScope(()=>setDistrict(district === name ? '' : name))}><span>{name}<strong>{average === null ? 'No records' : average+'%'}</strong></span><span className="preview-bar"><i style={{width:(average ?? 0)+'%'}}/></span><small>Average example compensation</small></button>;
      })}</div>}
      <div className="preview-scope" aria-live="polite"><span>{rows.length} example projects{pending || district ? ' · filtered' : ' · all records'}</span>{(pending || district) && <button onClick={()=>{setPending(false);setDistrict('');setSelected(null);}}><RotateCcw size={12}/> Reset</button>}</div>
      {(pending || district) && <div className="preview-chips">{pending && <button onClick={()=>changeScope(()=>setPending(false))}>Pending approvals <X size={12}/></button>}{district && <button onClick={()=>changeScope(()=>setDistrict(''))}>{district} <X size={12}/></button>}</div>}
      <div className="preview-records">{rows.length ? rows.map(p => <button key={p.id} aria-expanded={selected === p.id} aria-controls="preview-inspector" onClick={()=>setSelected(selected === p.id ? null : p.id)} className={selected === p.id ? 'is-selected' : ''}><span className="preview-record-id">{p.id}</span><span><strong>{p.name}</strong><small>{p.district} · {p.approvals} pending approvals</small></span><ArrowRight size={15}/></button>) : <p className="preview-empty">No examples in this scope. Reset filters to explore all three.</p>}</div>
      {active && <div className="preview-inspector" id="preview-inspector" key={active.id}><div><strong>{active.name}</strong><button aria-label="Close example details" onClick={()=>setSelected(null)}><X size={14}/></button></div>{[['Compensation',active.compensation],['Possession',active.possession]].map(([label,value])=><div className="preview-progress" key={label}><span>{label}<strong>{value}%</strong></span><span className="preview-bar" role="progressbar" aria-label={'Example '+label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><i style={{width:value+'%'}}/></span></div>)}<p>Illustrative observations only. No prediction or administrative action is generated.</p></div>}
    </div>
    <div className="preview-bottom"><span>Explore here. Sign in to work with project records.</span><Link to="/login" state={{from:view === 'Dashboard' ? '/dashboard' : view === 'Analytics' ? '/analytics' : '/projects'}}>Open {view.toLowerCase()} <ArrowRight size={13}/></Link></div>
  </section>;
}
