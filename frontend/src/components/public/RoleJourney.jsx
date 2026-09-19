import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Check } from 'lucide-react';

const journeys = [
  {title:'Start with the state portfolio.',tasks:['Compare acquisition progress across districts','Identify where approvals or disputes are concentrated','Open the relevant projects for administrative review'],scope:'Intended scope: assigned state and its districts.',route:'/analytics'},
  {title:'Bring local acquisition work into focus.',tasks:['Review the district’s recorded bottlenecks','Inspect compensation and possession progress','Coordinate follow-up on individual projects'],scope:'Intended scope: assigned district and its projects.',route:'/dashboard'},
  {title:'Keep assigned project records current.',tasks:['Locate the projects assigned to your agency','Update acquisition observations and progress','Review issues requiring coordination with officials'],scope:'Intended scope: explicitly assigned agency projects.',route:'/projects'},
  {title:'Give each person the right access.',tasks:['Verify the user’s department or agency affiliation','Approve the appropriate role and jurisdiction','Review access when responsibilities change'],scope:'Administrators can invite users, assign their initial scope and disable activated non-admin accounts.',route:'/admin/users'},
];
export default function RoleJourney({audiences}) {
  const [selected,setSelected] = useState(0);
  const journey = journeys[selected];
  return <div className="role-explorer"><div className="role-choices" aria-label="Choose your role">{audiences.map(([Icon,title],i)=><button key={title} aria-pressed={selected===i} onClick={()=>setSelected(i)}><Icon size={20}/><span>{title}</span>{selected===i ? <Check size={16}/> : <ArrowRight size={16}/>}</button>)}</div><div className="role-journey" key={selected} aria-live="polite"><p className="eyebrow">YOUR PROPOSED WORKFLOW</p><h3>{journey.title}</h3><ol>{journey.tasks.map(task=><li key={task}>{task}</li>)}</ol><p className="role-scope">{journey.scope}</p><Link className="button" to={journey.route ? '/login' : '/access'} state={journey.route ? {from:journey.route} : undefined}>{journey.route ? 'Sign in to the relevant view' : 'Explore access guidance'} <ArrowRight size={15}/></Link><small>Selecting a role here explains the workflow; it does not grant permissions.</small></div></div>;
}
