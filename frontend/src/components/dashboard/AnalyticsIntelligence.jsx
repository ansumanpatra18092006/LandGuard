import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowRight, BrainCircuit, CheckCircle2, CircleDot, Clock3, Crosshair,
  Gauge, Layers3, MapPinned, ShieldCheck, Target, UsersRound
} from 'lucide-react';
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, Scatter,
  ScatterChart, Tooltip, XAxis, YAxis, ZAxis
} from 'recharts';
import { pretty } from '../common';
import { useReducedMotion } from '../../hooks/useReducedMotion';

function toneFor(label = '') {
  const value = String(label).toUpperCase();
  if (value === 'CRITICAL') return 'critical';
  if (value === 'HIGH') return 'high';
  if (value === 'MODERATE' || value === 'WATCH' || value === 'MEDIUM') return 'medium';
  return 'low';
}

function InsightMetric({ icon: Icon, label, value, note, tone = 'neutral' }) {
  return <article className="analytics-kpi" data-tone={tone}>
    <div className="analytics-kpi-icon"><Icon size={18}/></div>
    <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
  </article>;
}

function RiskTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return <div className="analytics-scatter-tooltip">
    <strong>{row.project_name}</strong>
    <span>{row.project_id}</span>
    <div><b>Acquisition risk</b><em>{row.risk}/100</em></div>
    <div><b>Readiness</b><em>{row.readiness}/100</em></div>
    <div><b>Priority</b><em>{row.priority}/100</em></div>
    <div><b>PAIMANA signal</b><em>{row.schedule}%</em></div>
  </div>;
}


function MeasuredScatterMatrix({ groups, reducedMotion }) {
  const hostRef = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 330 });

  useEffect(() => {
    const node = hostRef.current;
    if (!node) return undefined;

    const measure = () => {
      const rect = node.getBoundingClientRect();
      const width = Math.floor(rect.width);
      const height = Math.floor(rect.height);
      if (width > 0 && height > 0) {
        setSize(previous => previous.width === width && previous.height === height
          ? previous
          : { width, height });
      }
    };

    measure();

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const ready = size.width >= 40 && size.height >= 180;

  return <div className="analytics-matrix-wrap" ref={hostRef}>
    {ready ? <ScatterChart width={size.width} height={size.height} margin={{ top: 10, right: 20, bottom: 8, left: 0 }} accessibilityLayer>
      <ReferenceArea x1={0} x2={55} y1={50} y2={100} fill="var(--risk-high-soft)" fillOpacity={0.45}/>
      <CartesianGrid stroke="var(--border)" strokeDasharray="3 6" strokeOpacity={0.75}/>
      <XAxis type="number" dataKey="readiness" domain={[0,100]} ticks={[0,25,50,75,100]} tick={{fontSize:10,fill:'var(--text-muted)'}} tickLine={false} axisLine={false} label={{ value:'Acquisition readiness →', position:'insideBottom', offset:-3, fontSize:10, fill:'var(--text-muted)' }}/>
      <YAxis type="number" dataKey="risk" domain={[0,100]} ticks={[0,25,50,75,100]} tick={{fontSize:10,fill:'var(--text-muted)'}} tickLine={false} axisLine={false} width={34}/>
      <ZAxis type="number" dataKey="z" range={[70,230]}/>
      <ReferenceLine x={55} stroke="var(--border-strong)" strokeDasharray="4 5"/>
      <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="4 5"/>
      <Tooltip cursor={{ strokeDasharray:'3 3' }} content={<RiskTooltip/>}/>
      {groups.map(group => group.rows.length ? <Scatter key={group.category} name={group.category} data={group.rows} fill={`var(--analytics-${toneFor(group.category)})`} isAnimationActive={!reducedMotion} animationDuration={450}/> : null)}
    </ScatterChart> : <div className="analytics-chart-placeholder" aria-hidden="true"/>}
    <span className="analytics-review-zone"><Crosshair size={12}/> Review zone</span>
  </div>;
}

function RiskReadinessMatrix({ projects }) {
  const reducedMotion = useReducedMotion();
  const data = projects.map(p => ({
    ...p,
    risk: p.acquisition_delay_risk_score ?? 0,
    readiness: p.acquisition_readiness_score ?? 0,
    priority: p.intervention_priority_score ?? 0,
    schedule: Math.round((p.delay_probability ?? 0) * 100),
    z: Math.max(65, (p.intervention_priority_score ?? 0) * 2.2),
  }));
  const groups = ['CRITICAL','HIGH','WATCH','ROUTINE'].map(category => ({
    category,
    rows: data.filter(row => (row.intervention_priority_category || 'ROUTINE') === category),
  }));
  return <section className="panel analytics-matrix-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">PORTFOLIO PATTERN</span><h2>Risk × readiness matrix</h2><p>Upper-left projects combine higher acquisition risk with lower readiness — the clearest review zone.</p></div><div className="analytics-legend"><span className="critical">Critical</span><span className="high">High</span><span className="medium">Watch</span><span className="low">Routine</span></div></div>
    <MeasuredScatterMatrix groups={groups} reducedMotion={reducedMotion}/>
  </section>;
}


function DelayTrendPanel({ districtTrends = [], stateTrends = [] }) {
  const districtLabels = [...new Set(districtTrends.map(row => row.group_label))].slice(0, 5);
  const stateLabels = [...new Set(stateTrends.map(row => row.group_label))].slice(0, 4);
  const useStates = districtLabels.length <= 1 && stateLabels.length > 1;
  const rows = useStates ? stateTrends : districtTrends;
  const labels = useStates ? stateLabels : districtLabels;
  const periods = [...new Set(rows.map(row => row.period))].sort();
  const data = periods.map(period => {
    const point = { period };
    rows.filter(row => row.period === period && labels.includes(row.group_label)).forEach(row => {
      point[row.group_label] = row.avg_acquisition_risk_score;
    });
    return point;
  });
  const strokes = ['var(--primary)', 'var(--teal)', 'var(--risk-medium)', 'var(--slate)', 'var(--risk-high)'];
  return <section className="panel analytics-trend-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">DELAY TREND</span><h2>{useStates ? 'State-wise risk trend' : 'District-wise risk trend'}</h2><p>Historical LandGuard snapshots show how the transparent acquisition-delay risk index changes as project records are updated.</p></div><span className="analytics-total-pill">{data.length} dates</span></div>
    {data.length ? <div className="analytics-trend-chart"><LineChart width={760} height={280} data={data} margin={{top:10,right:22,bottom:4,left:-8}} accessibilityLayer>
      <CartesianGrid stroke="var(--border)" strokeDasharray="3 6"/>
      <XAxis dataKey="period" tick={{fontSize:10,fill:'var(--text-muted)'}} tickLine={false} axisLine={false}/>
      <YAxis domain={[0,100]} ticks={[0,25,50,75,100]} tick={{fontSize:10,fill:'var(--text-muted)'}} tickLine={false} axisLine={false}/>
      <Tooltip formatter={(value,name)=>[`${Number(value).toFixed(1)}/100`,name]}/>
      <Legend wrapperStyle={{fontSize:11}}/>
      {labels.map((label,index)=><Line key={label} type="monotone" dataKey={label} stroke={strokes[index % strokes.length]} strokeWidth={2.2} dot={{r:3}} connectNulls isAnimationActive={false}/>) }
    </LineChart></div> : <p className="analytics-empty-copy">Trend history begins when projects are created or updated in this version. Existing records receive a baseline snapshot during migration.</p>}
    <p className="analytics-panel-note">This trend uses LandGuard's transparent acquisition-risk index. A calibrated stage-specific ML trend requires authoritative labelled acquisition history.</p>
  </section>;
}


function MlExplainabilityHeatmap({ projects }) {
  const rows = [...projects]
    .filter(project => Array.isArray(project.ml_factors) && project.ml_factors.length)
    .sort((a,b) => (b.delay_probability || 0) - (a.delay_probability || 0))
    .slice(0, 7);
  const totals = new Map();
  rows.forEach(project => project.ml_factors.forEach(factor => {
    totals.set(factor.display_name, (totals.get(factor.display_name) || 0) + Number(factor.contribution || 0));
  }));
  const columns = [...totals.entries()].sort((a,b) => b[1]-a[1]).slice(0, 6).map(([name]) => name);
  const maxContribution = Math.max(0.0001, ...rows.flatMap(project => project.ml_factors.map(factor => Number(factor.contribution || 0))));

  function cellFor(project, label) {
    const factor = project.ml_factors.find(item => item.display_name === label);
    if (!factor) return <span className="ml-heat-cell empty" title="No material local contribution for this project">—</span>;
    const strength = Math.max(0.12, Math.min(1, Number(factor.contribution || 0) / maxContribution));
    const riskUp = factor.direction === 'increases_risk';
    return <span
      className={`ml-heat-cell ${riskUp ? 'risk-up' : 'risk-down'}`}
      style={{'--heat-alpha': strength}}
      title={`${factor.display_name}: ${riskUp ? 'increases' : 'reduces'} ML schedule-slip risk · local contribution ${Number(factor.contribution || 0).toFixed(3)}`}
    >{riskUp ? '↑' : '↓'}</span>;
  }

  return <section className="panel analytics-ml-heatmap-panel">
    <div className="section-title analytics-section-title">
      <div><span className="eyebrow"><BrainCircuit size={13}/> ML EXPLAINABILITY</span><h2>What is driving the ML signal?</h2><p>Local PAIMANA model factors across the highest-risk projects. Darker cells mean stronger influence; arrows show direction.</p></div>
      <div className="ml-heat-key"><span className="up">↑ raises risk</span><span className="down">↓ reduces risk</span></div>
    </div>
    {rows.length && columns.length ? <div className="ml-heat-scroll"><div className="ml-heat-grid" style={{'--ml-columns': columns.length}}>
      <div className="ml-heat-corner">Project</div>
      {columns.map(label => <div className="ml-heat-col" key={label} title={label}>{label}</div>)}
      {rows.map(project => <div className="ml-heat-row" key={project.project_id}>
        <div className="ml-heat-project"><strong>{project.project_name}</strong><small>{Math.round((project.delay_probability || 0)*100)}% ML risk</small></div>
        {columns.map(label => <div className="ml-heat-slot" key={label}>{cellFor(project,label)}</div>)}
      </div>)}
    </div></div> : <p className="analytics-empty-copy">ML explanation cells become available when the PAIMANA model can score projects in this scope.</p>}
    <p className="analytics-panel-note"><b>Important:</b> this explains the PAIMANA schedule-slip model. Land-acquisition factors such as compensation, possession, legal disputes and approvals remain in LandGuard's separate transparent acquisition-risk lane.</p>
  </section>;
}

function BottleneckPanel({ projects }) {
  const counts = new Map();
  projects.forEach(p => {
    const label = p.primary_bottleneck || 'Operational review';
    counts.set(label, (counts.get(label) || 0) + 1);
  });
  const rows = [...counts.entries()].sort((a,b) => b[1]-a[1]);
  const max = Math.max(1, ...rows.map(([,count]) => count));
  return <section className="panel analytics-bottleneck-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">WHY RISK EXISTS</span><h2>Dominant bottlenecks</h2><p>Primary blocker attached to each model-ready project.</p></div></div>
    <div className="analytics-bottlenecks">
      {rows.length ? rows.map(([label,count], index) => <div className="analytics-bottleneck" key={label}>
        <div className="analytics-bottleneck-label"><span>{String(index + 1).padStart(2,'0')}</span><strong>{label}</strong><b>{count}</b></div>
        <div className="analytics-bottleneck-track"><i style={{width:`${count/max*100}%`}}/></div>
      </div>) : <p className="analytics-empty-copy">No bottleneck evidence is available for this scope.</p>}
    </div>
    <p className="analytics-panel-note">Counts describe the strongest current blocker per scored project; they are not probabilities.</p>
  </section>;
}

function StagePipeline({ stages, total }) {
  const order = ['NOTIFICATION','SURVEY','VALUATION','COMPENSATION','REHABILITATION','POSSESSION','COMPLETED'];
  const lookup = new Map(stages.map(row => [row.stage, row.count]));
  const visible = order.filter(stage => lookup.has(stage));
  const display = visible.length ? visible : stages.map(row => row.stage);
  return <section className="panel analytics-stage-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">PROCESS POSITION</span><h2>Acquisition stage pipeline</h2><p>Where the current portfolio sits in the acquisition workflow.</p></div><span className="analytics-total-pill">{total} projects</span></div>
    <div className="analytics-stage-flow">
      {display.map((stage,index) => {
        const count = lookup.get(stage) || 0;
        return <div className="analytics-stage-node" key={stage} data-active={count > 0}>
          <span>{String(index + 1).padStart(2,'0')}</span><strong>{pretty(stage)}</strong><b>{count}</b>
        </div>;
      })}
    </div>
  </section>;
}

function PriorityQueue({ projects }) {
  const top = [...projects].sort((a,b) => (b.intervention_priority_score || 0) - (a.intervention_priority_score || 0)).slice(0,5);
  return <section className="panel analytics-priority-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">NEXT OFFICER ATTENTION</span><h2>Priority projects</h2><p>Acquisition risk sets the base; PAIMANA schedule evidence can only escalate priority.</p></div></div>
    <div className="analytics-priority-list">
      {top.map((p,index) => <Link key={p.project_id} to={`/projects/${p.project_id}?tab=twin`} className="analytics-priority-row">
        <span className="analytics-rank">{String(index + 1).padStart(2,'0')}</span>
        <div className="analytics-priority-name"><strong>{p.project_name}</strong><small>{p.primary_bottleneck || 'Operational review'} · {p.project_id}</small></div>
        <div className="analytics-mini-metrics"><span><b>{p.acquisition_delay_risk_score ?? '—'}</b>risk</span><span><b>{p.acquisition_readiness_score ?? '—'}</b>ready</span><span><b>{Math.round((p.delay_probability || 0)*100)}%</b>ML</span></div>
        <div className={`analytics-priority-score ${toneFor(p.intervention_priority_category)}`}><strong>{p.intervention_priority_score ?? '—'}</strong><small>{p.intervention_priority_category || 'ROUTINE'}</small></div>
        <ArrowRight size={16}/>
      </Link>)}
    </div>
  </section>;
}

function InterventionHealth({ ledger }) {
  const open = ledger?.open_count || 0;
  const progress = ledger?.in_progress_count || 0;
  const resolved = ledger?.resolved_count || 0;
  const overdue = ledger?.overdue_count || 0;
  const total = Math.max(1, open + progress + resolved);
  return <section className="panel analytics-intervention-panel">
    <div className="section-title analytics-section-title"><div><span className="eyebrow">ACCOUNTABILITY</span><h2>Intervention health</h2><p>Tracked administrative actions across the current officer scope.</p></div></div>
    <div className="analytics-ledger-summary">
      <div><Clock3 size={17}/><strong>{open}</strong><span>Open</span></div>
      <div><CircleDot size={17}/><strong>{progress}</strong><span>In progress</span></div>
      <div><CheckCircle2 size={17}/><strong>{resolved}</strong><span>Resolved</span></div>
      <div className={overdue ? 'attention' : ''}><AlertTriangle size={17}/><strong>{overdue}</strong><span>Overdue</span></div>
    </div>
    <div className="analytics-ledger-bar" aria-label={`${open} open, ${progress} in progress, ${resolved} resolved`}>
      <i className="open" style={{width:`${open/total*100}%`}}/><i className="progressing" style={{width:`${progress/total*100}%`}}/><i className="resolved" style={{width:`${resolved/total*100}%`}}/>
    </div>
    <Link className="analytics-text-link" to="/projects">Open projects and track actions <ArrowRight size={14}/></Link>
  </section>;
}

export default function AnalyticsIntelligence({ summary, districts, stages, pulse, ledger, districtTrends = [], stateTrends = [] }) {
  const projects = pulse?.projects || [];
  const avgReadiness = projects.length ? Math.round(projects.reduce((sum,p) => sum + (p.acquisition_readiness_score || 0),0)/projects.length) : 0;
  const highAcquisition = projects.filter(p => ['HIGH','CRITICAL'].includes(p.acquisition_delay_risk_label)).length;
  const urgent = projects.filter(p => ['HIGH','CRITICAL'].includes(p.intervention_priority_category)).length;
  const avgPossession = districts.length ? Math.round(districts.reduce((sum,d) => sum + d.avg_possession_pct * d.project_count,0) / Math.max(1,districts.reduce((sum,d)=>sum+d.project_count,0))) : 0;
  const blockerCounts = projects.reduce((acc,p) => { const k=p.primary_bottleneck||'Operational review'; acc[k]=(acc[k]||0)+1; return acc; },{});
  const dominant = Object.entries(blockerCounts).sort((a,b)=>b[1]-a[1])[0];
  const scope = districts.length === 1 ? `${districts[0].district}, ${districts[0].state}` : `${districts.length} districts`;
  const insight = dominant
    ? `${dominant[0]} is the most common primary blocker (${dominant[1]} of ${projects.length} model-ready projects). ${urgent ? `${urgent} project${urgent === 1 ? '' : 's'} currently sit in HIGH/CRITICAL intervention priority.` : 'No project is currently in HIGH/CRITICAL intervention priority.'}`
    : 'Portfolio intelligence becomes available when model-ready projects are present in the selected scope.';

  return <div className="analytics-command-center">
    <section className="analytics-hero panel">
      <div className="analytics-hero-copy"><span className="eyebrow"><Target size={13}/> PORTFOLIO INTELLIGENCE</span><h2>{scope}</h2><p>One operational picture: acquisition condition first, independent PAIMANA schedule evidence second, accountable intervention next.</p></div>
      <div className="analytics-hero-badge"><ShieldCheck size={18}/><span>Current database observations</span></div>
    </section>

    <div className="analytics-kpi-grid">
      <InsightMetric icon={AlertTriangle} label="High / critical acquisition risk" value={highAcquisition} note={`of ${projects.length || summary.total_projects} model-ready projects`} tone={highAcquisition ? 'red' : 'green'}/>
      <InsightMetric icon={Gauge} label="Average acquisition readiness" value={`${avgReadiness}/100`} note="Transparent process-readiness index" tone="teal"/>
      <InsightMetric icon={Crosshair} label="Immediate intervention" value={urgent} note="HIGH / CRITICAL priority" tone={urgent ? 'amber' : 'green'}/>
      <InsightMetric icon={AlertTriangle} label="Overdue tracked actions" value={ledger?.overdue_count ?? 0} note={`${ledger?.open_count ?? 0} open · ${ledger?.in_progress_count ?? 0} in progress`} tone={(ledger?.overdue_count || 0) ? 'red' : 'green'}/>
    </div>

    <div className="analytics-intelligence-grid">
      <RiskReadinessMatrix projects={projects}/>
      <BottleneckPanel projects={projects}/>
    </div>

    <MlExplainabilityHeatmap projects={projects}/>
    <DelayTrendPanel districtTrends={districtTrends} stateTrends={stateTrends}/>

    <section className="analytics-insight-strip">
      <div><Layers3 size={18}/><span className="eyebrow">PORTFOLIO INSIGHT</span><strong>{insight}</strong></div>
      <div className="analytics-insight-facts"><span><b>{summary.avg_compensation_pct ?? '—'}%</b> avg compensation</span><span><b>{avgPossession}%</b> avg possession</span><span><b>{summary.pending_approvals}</b> pending approvals</span><span><b>{summary.projects_with_legal_disputes}</b> projects with disputes</span></div>
    </section>

    <StagePipeline stages={stages} total={summary.total_projects}/>

    <div className="analytics-action-grid">
      <PriorityQueue projects={projects}/>
      <InterventionHealth ledger={ledger}/>
    </div>

    <div className="analytics-data-note"><UsersRound size={14}/><span>Acquisition indices are transparent decision-support measures, not probabilities. PAIMANA is shown separately as schedule evidence. Illustrative demo records remain labelled as illustrative.</span><Link to="/map"><MapPinned size={14}/> Open GIS</Link></div>
  </div>;
}
