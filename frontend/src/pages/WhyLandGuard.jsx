import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ExternalLink, CheckCircle2, FlaskConical } from 'lucide-react';
import { PublicHeader } from './Landing';
import '../styles/why-landguard.css';

const sources = {
  bhoomi: {name:'Bhoomi Rashi · MoRTH',url:'https://bhoomirashi.gov.in/',note:'Official portal; reviewed 16 September 2026'},
  parivesh: {name:'PARIVESH · MoEFCC',url:'https://parivesh.nic.in/mobile/privacy_policy.html',note:'Official description of clearance services; reviewed 16 September 2026'},
  pmg: {name:'PMG · DPIIT',url:'https://pmg.dpiit.gov.in/',note:'Official features and eligibility; reviewed 16 September 2026'},
  dpiit: {name:'DPIIT annual report 2024–25',url:'https://www.dpiit.gov.in/static/uploads/2025/06/3d9c9c2daeefb97bb9ce964370938b71.pdf',note:'Sections 1.7.2–1.7.4: coverage and proactive milestone monitoring'},
  cag: {name:'CAG Report 19 of 2023',url:'https://cag.gov.in/uploads/download_audit_report/2023/Report-No.-19-of-203--Bharatmala-English-064d5db7bc63c20.06754442.pdf#page=149',note:'Chapter 6, printed pp. 120–121: historical audit findings'}
};
const opportunities = [
  {id:'readiness',name:'Acquisition readiness',basis:'Documented execution problem',title:'Spot unresolved prerequisites before the next milestone.',
   evidence:'CAG’s 2023 Bharatmala audit linked delayed right-of-way handover to delayed project commencement and progress. This is historical evidence of an execution problem, not a test of today’s portals.',sources:['cag'],
   gap:'Recording a project’s status does not, by itself, ensure the land needed for the next milestone is available.',
   now:'LandGuard filters projects by compensation lag, possession lag, pending approvals and disputes. Officials can open the records behind each indicator.',
   next:'Add dated milestone prerequisites, evidence attachments, a responsible official and due dates. Flag missing evidence and overdue reviews for human follow-up.',
   measure:'In a pilot, measure warning lead time, overdue prerequisites and time from flag to official review. Compare with the same team’s baseline.',
   action:'Inspect the dashboard',route:'/dashboard'},
  {id:'context',name:'Connected context',basis:'Design hypothesis to validate',title:'Review related acquisition facts in one place.',
   evidence:'Bhoomi Rashi focuses on highway acquisition, PARIVESH on green clearances, and PMG on project issues and coordination. These distinct mandates suggest a useful local review view; they do not prove that the systems lack integration.',sources:['bhoomi','parivesh','pmg'],
   gap:'Our hypothesis: officials could spend less time reconciling acquisition facts when their local review has consistent project identifiers and source references.',
   now:'One project record brings together compensation, possession, rehabilitation, approvals and disputes, with district comparisons. Data is currently entered in LandGuard; government feeds are not connected.',
   next:'With agency permission, add imports or API connectors, source IDs, source timestamps and reconciliation checks. Keep statutory decisions and payments in the authorized systems.',
   measure:'Ask officials to complete the same review with and without LandGuard. Measure preparation time, duplicate entry and unresolved data mismatches.',
   action:'Explore project records',route:'/projects'},
  {id:'coverage',name:'Local portfolio review',basis:'Documented scope boundary',title:'Support routine review across an assigned district.',
   evidence:'PMG’s published scope emphasizes projects worth ₹500 crore or more, with exceptions for specified critical and special-category projects. It already supports issue tracking and proactive milestone monitoring.',sources:['dpiit'],
   gap:'There is an opportunity to test a lightweight acquisition workflow for local portfolios outside that principal remit. This does not mean those projects lack other state or departmental systems.',
   now:'LandGuard supports state, district and assigned-project views without an investment-value eligibility threshold. Officers see only their assigned records and aggregates.',
   next:'Pilot with one district, map its existing state-system workflow, and add review queues and handoff reports only where officials identify duplication or a missing step.',
   measure:'Measure review coverage across the agreed pilot portfolio, time to locate a blocking record and adoption by authorized officials.',
   action:'Compare district records',route:'/analytics'},
  {id:'trust',name:'Trustworthy early warning',basis:'LandGuard’s own validation gap',title:'Make every warning explainable—and test whether it helps.',
   evidence:'LandGuard now uses real longitudinal MoSPI PAIMANA snapshots for a forward schedule-slip baseline. It still does not have validated longitudinal land-acquisition outcome data, so acquisition risk, readiness and friction remain transparent operational decision-support logic rather than a learned land-acquisition probability.',sources:[],
   gap:'An attractive risk score is insufficient evidence for an administrative decision. Explanations also do not establish causation.',
   now:'The prototype separates a PAIMANA-trained schedule signal from land-acquisition friction/readiness, exposes model provenance and explanations, ranks intervention priority, and lets officers convert recommendations into tracked interventions while leaving decisions with authorized officials.',
   next:'Obtain approved longitudinal acquisition-stage outcomes, add stage-event history, evaluate future land-acquisition models on unseen projects and districts, and compare them against the current transparent friction/readiness baselines before any operational claim.',
   measure:'For the PAIMANA baseline, report conservative temporal/grouped validation and uncertainty. For future acquisition models, report precision, recall, calibration, warning lead time, false alarms and reviewer workload. No acquisition-delay reduction claim is made from the current prototype.',
   action:'Explore the public walkthrough',route:'/#workspace'}
];
function SourceLink({id}) {
  const source=sources[id];
  return <a href={source.url} target="_blank" rel="noopener noreferrer">{source.name} <ExternalLink size={12}/></a>;
}
export default function WhyLandGuard() {
  const [selected,setSelected]=useState('readiness');
  const item=opportunities.find(x=>x.id===selected);
  return <div className="public-site"><a className="skip-link" href="#why-main">Skip to main content</a><PublicHeader/>
    <main id="why-main" className="why-page">
      <section className="why-hero"><p className="eyebrow">THE PROBLEM, THE EVIDENCE, THE PROPOSAL</p><h1>Better acquisition reviews.<br/><em>A clear role for LandGuard.</em></h1><p className="hero-intro">Official platforms already digitize important workflows. Our proposal is a focused decision-support workspace that helps administrative teams review acquisition readiness and evaluate early warnings.</p><div className="public-actions"><a className="button primary" href="#opportunities">Explore the opportunities <ArrowRight size={16}/></a><Link className="button" to="/#workspace">Try the prototype</Link></div><p className="public-caption">Public-source review · 16 September 2026 · No government integration or endorsement claimed</p></section>
      <section className="public-section"><p className="eyebrow">WHAT ALREADY EXISTS</p><h2>Build on established capabilities.</h2><div className="existing-systems">
        <article><span>01 / ACQUISITION</span><h3>Bhoomi Rashi</h3><p>MoRTH’s highway land-acquisition portal includes acquisition monitoring and online compensation disbursement.</p><SourceLink id="bhoomi"/></article>
        <article><span>02 / CLEARANCES</span><h3>PARIVESH</h3><p>MoEFCC’s services support environmental, forest, wildlife and coastal regulation zone clearances.</p><SourceLink id="parivesh"/></article>
        <article><span>03 / COORDINATION</span><h3>Project Monitoring Group</h3><p>DPIIT’s portal already provides project dashboards, issue tracking, follow-up and stakeholder feedback.</p><SourceLink id="pmg"/></article>
      </div><p className="why-method">This is a review of public documentation, not a hands-on audit of restricted government systems. An undocumented feature is not treated as an absent feature. Proposed benefits still need validation with officials.</p></section>
      <section className="public-section" id="opportunities"><p className="eyebrow">FROM LIMITATION TO PROPOSAL</p><h2>Where we can add value.</h2><p className="muted">Choose an opportunity to see its evidence, the current response and the work still required.</p>
        <div className="opportunity-options" role="group" aria-label="Choose an opportunity">{opportunities.map((entry,i)=><button key={entry.id} aria-pressed={selected===entry.id} aria-controls="opportunity-detail" onClick={()=>setSelected(entry.id)}><span>0{i+1}</span>{entry.name}<ArrowRight size={16}/></button>)}</div>
        <article id="opportunity-detail" className="opportunity-detail" aria-live="polite" aria-atomic="true"><span className="evidence-badge">{item.basis}</span><h3>{item.title}</h3><p>{item.gap}</p>
          <div className="opportunity-evidence"><strong>Evidence and interpretation</strong><p>{item.evidence}</p><div className="source-links">{item.sources.map(id=><SourceLink key={id} id={id}/>)}</div></div>
          <div className="proposal-pair"><section><p className="proposal-label"><CheckCircle2 size={17}/> Working prototype</p><h4>What LandGuard does today</h4><p>{item.now}</p></section><section><p className="proposal-label proposed"><FlaskConical size={17}/> Proposed extension</p><h4>What we would build next</h4><p>{item.next}</p></section></div>
          <div className="pilot-measure"><strong>How we would validate the benefit</strong><p>{item.measure}</p></div>
          <Link className="button primary" to={item.route.startsWith('/#')?item.route:'/login'} state={item.route.startsWith('/#')?undefined:{from:item.route}}>{item.action} <ArrowRight size={16}/></Link>
        </article>
      </section>
      <section className="public-section"><p className="eyebrow">A PRACTICAL FIRST PILOT</p><h2>Start with evidence, then expand.</h2><ol className="pilot-steps"><li><strong>Understand the review</strong><p>Work with one district’s officials to identify their existing tools, missing evidence and repeated manual tasks.</p></li><li><strong>Improve readiness review</strong><p>Prioritize dated prerequisites, responsible officials and source evidence. Compare review time and follow-through against the baseline.</p></li><li><strong>Validate prediction separately</strong><p>Evaluate approved historical outcomes before exposing model scores in a supervised operational pilot.</p></li></ol><p className="why-method">The prototype does not determine compensation, establish legal title, approve clearances or resolve disputes. These responsibilities stay with the relevant authorities. Institutional rollout also needs live identity verification, data agreements and security review.</p></section>
      <section className="public-section why-references"><h2>Sources you can inspect</h2><ul>{Object.entries(sources).map(([id,source])=><li key={id}><SourceLink id={id}/><small>{source.note}</small></li>)}</ul><Link className="back" to="/">← Back to LandGuard AI</Link></section>
    </main><footer className="public-footer"><span>LANDGUARD AI · Research-informed prototype</span><span>AI recommends; authorized officials decide.</span></footer>
  </div>;
}
