import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useRevealProps } from '../hooks/useReveal';
import { useSpotlight } from '../hooks/useSpotlight';
import { useTilt } from '../hooks/useTilt';
import { useMagnetic } from '../hooks/useMagnetic';
import { useAnimatedNumber } from '../hooks/useAnimatedNumber';
import { combineFX } from '../utils/combineFX';
import ProductPreview, { previewViews } from '../components/public/ProductPreview';
import RoleJourney from '../components/public/RoleJourney';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Building2, MapPinned, BriefcaseBusiness, Users, ClipboardList, ChartNoAxesCombined, FolderOpen } from 'lucide-react';
import '../public.css';
import '../styles/why-landguard.css';
import '../public-interactions.css';

export const audiences = [
  [Building2,'State officers','Review the state portfolio, compare districts, and coordinate escalations.'],
  [MapPinned,'District officers','Track local acquisition progress, approvals, compensation, and disputes.'],
  [BriefcaseBusiness,'Implementing agencies','Maintain assigned project records and respond to administrative follow-up.'],
  [Users,'Portal administrators','Manage approved accounts, responsibilities, and access boundaries.'],
];

const workspaceCards = [
  [ClipboardList,'Dashboard','What needs my attention?','Portfolio indicators, administrative bottlenecks, and a project queue.'],
  [ChartNoAxesCombined,'Analytics','Where are the differences?','District comparisons and acquisition-stage distributions, with filters that carry into project records.'],
  [FolderOpen,'Projects','What is happening on this project?','Searchable records, quick inspection, acquisition progress, and project updates.'],
];

export function PublicHeader() {
  const header = useRef(null);
  useEffect(() => {
    let frame;
    const update = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => { const range = document.documentElement.scrollHeight - innerHeight; header.current?.style.setProperty('--scroll-progress',range > 0 ? String(Math.min(1,scrollY/range)) : '0'); }); };
    update(); window.addEventListener('scroll',update,{passive:true}); window.addEventListener('resize',update);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('scroll',update); window.removeEventListener('resize',update); };
  },[]);
  return <header ref={header} className="public-header"><Link className="public-brand" to="/" aria-label="LandGuard AI home"><ShieldCheck size={27}/><span>LANDGUARD <b>AI</b></span></Link><nav aria-label="Public navigation"><a href="/#workspace">The workspace</a><a href="/#users">Who it serves</a><Link to="/why-landguard">Why LandGuard</Link><Link to="/access">Access guidance</Link></nav><Link className="button primary" to="/login">Sign in <ArrowRight size={15}/></Link><span className="public-scroll-progress" aria-hidden="true"/></header>;
}

// A single count-up figure for the hero's trust row. Reserved for numbers the site can
// stand behind literally — counts of what's actually in the walkthrough below, not
// invented traction metrics. That keeps it consistent with the honesty this prototype
// insists on everywhere else ("illustrative", "not a validated forecast").
function HeroStat({ target, label }) {
  const value = useAnimatedNumber(target, 900);
  return <div><strong>{Math.round(value)}</strong><span>{label}</span></div>;
}

// One workspace card: pointer spotlight (tint) plus a subtle tilt, combined via
// combineFX so both hooks can share the same ref and pointer handlers. Falls back to a
// plain button with no extra props on touch devices and under reduced motion.
function WorkspaceCard({ icon: Icon, title, question, copy, active, onClick, index }) {
  const fx = combineFX(useSpotlight(), useTilt(5));
  return <button {...fx} style={{ '--index': index }} aria-pressed={active} onClick={onClick}>
    <Icon size={23}/><h3>{title}</h3><strong>{question}</strong><p>{copy}</p>
    <span className="public-card-action">Try this view <ArrowRight size={14}/></span>
  </button>;
}

export default function Landing() {
  const [view,setView] = useState('Dashboard');
  const reduced = useReducedMotion();
  const workspaceReveal = useRevealProps('public-section public-reveal');
  const rolesReveal = useRevealProps('public-section audience-section public-reveal');
  const magnetic = useMagnetic();
  function preview(name) {
    setView(name);
    document.getElementById('product-preview')?.scrollIntoView({behavior:reduced ? 'instant' : 'smooth',block:'start'});
    document.getElementById('preview-tab-'+previewViews.indexOf(name))?.focus({preventScroll:true});
  }
  return <div className="public-site"><a className="skip-link" href="#public-main">Skip to main content</a><PublicHeader/><main id="public-main">
    <section className="landing-hero"><div aria-hidden="true" className="hero-aurora"/><div><div className="public-kicker"><span/> LAND ACQUISITION · DECISION SUPPORT</div><h1>See the blockers.<br/><em className="hero-shine">Move projects forward.</em></h1><p className="hero-intro">One workspace for acquisition records, administrative bottlenecks, and district comparisons. Built for the officials and agencies responsible for moving projects forward.</p><div className="public-actions"><Link {...magnetic} className="button primary" to="/login">Sign in to the prototype <ArrowRight size={17}/></Link><a className="button" href="#workspace">Explore the workflow</a></div><div className="hero-stats"><HeroStat target={previewViews.length} label="Interactive views to try below, no sign-in needed"/><HeroStat target={audiences.length} label="Role journeys mapped to real responsibilities"/><HeroStat target={0} label="Real workspace records touched by the walkthrough"/></div><p className="public-caption">Hackathon prototype · Illustrative records · Not an official government service</p></div>
    <ProductPreview view={view} onView={setView}/></section>
    <section className="why-teaser" aria-label="Why LandGuard"><div><p className="eyebrow">BUILT AROUND A SPECIFIC NEED</p><h2>From acquisition status to an informed review.</h2><p>Explore the existing government platforms, documented execution challenges, and the improvements we propose—with a clear distinction between working features and future work.</p></div><Link className="button" to="/why-landguard">Evidence & proposal <ArrowRight size={16}/></Link></section>
    <section {...workspaceReveal} id="workspace"><div className="public-section-heading"><div><p className="eyebrow">ONE PORTAL, DISTINCT PURPOSES</p><h2>The right view for each task.</h2></div><p>Start with priorities. Investigate a pattern. Open the records behind it.</p></div><div className="public-cards">{workspaceCards.map(([Icon,title,question,copy],index) => <WorkspaceCard key={title} icon={Icon} title={title} question={question} copy={copy} active={view === title} onClick={()=>preview(title)} index={index}/>)}</div></section>
    <section {...rolesReveal} id="users"><div className="public-section-heading"><div><p className="eyebrow">DESIGNED FOR ADMINISTRATIVE TEAMS</p><h2>Shared visibility.<br/>Defined responsibility.</h2></div><p>The intended portal is for authorized departmental users and implementing agencies. It is not a public land-claim or compensation application service.</p></div><RoleJourney audiences={audiences}/><p className="public-caption">Role selection explains the workflow. Actual access is assigned by an administrator and enforced by the backend.</p></section>
    <section className="access-banner"><div><p className="eyebrow">ACCESS BY RESPONSIBILITY</p><h2>An approved account.<br/>A defined project scope.</h2><p>A designated administrator verifies your responsibility, assigns your scope, and sends an invitation to your work email.</p><Link className="button" to="/access">How to get access <ArrowRight size={16}/></Link></div><div className="prototype-note"><strong>Where the prototype stands</strong><p>Project records, operational analytics, a coordinate preview, and an artifact-based model pipeline are implemented. Any synthetic-model results are demonstrations, not validated forecasts.</p><p>Account access uses Supabase Auth, administrator invitations through Brevo, and enforced jurisdiction controls. This instance must be configured before invitations can be sent. Departmental SSO and MFA are not yet connected.</p></div></section>
    <section className="public-section"><p className="eyebrow">BEFORE YOU ENTER</p><h2>A few useful answers.</h2><div className="public-faq"><details><summary>Can I try it without signing in?</summary><p>Yes. The interactive walkthrough above uses three fictional examples. You can filter approvals, compare example districts, and open a record. It does not read or change workspace data.</p></details><details><summary>Does selecting a role create an account?</summary><p>No. The role explorer shows the intended workflow. An administrator must invite you and assign your jurisdiction in the Users & access page.</p></details><details><summary>Are model results verified predictions?</summary><p>The current synthetic-model demonstration is not validated on real government acquisition outcomes. Administrative decisions remain with authorized officials.</p></details></div></section>
  </main><footer className="public-footer"><span>LANDGUARD AI · Hackathon prototype</span><span>Decision support, with human accountability.</span></footer></div>;
}
