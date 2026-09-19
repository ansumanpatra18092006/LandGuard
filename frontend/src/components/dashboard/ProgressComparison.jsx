import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { SectionCard, InfoTooltip } from '../common';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { DrillBar, AnalyticsTooltip } from './ChartInteraction';

export default function ProgressComparison({ districts,onSelect,isSelected }) {
  const data = districts.map(row => ({ ...row,label:row.district + ', ' + row.state }));
  const reducedMotion = useReducedMotion();
  return <SectionCard className="comparison-panel" title="Compensation vs. possession" description="Select a district to explore its projects" action={<InfoTooltip text="Unweighted project averages from the database. Select either bar to filter by its district and state."/>}>
    <div className="chart-legend"><span><i/> Compensation</span><span><i/> Possession</span><small>Average completion (%)</small></div>
    <div className="chart-scroll"><div className="chart-canvas" style={{ height:Math.max(285,data.length * 53) }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={data} layout="vertical" margin={{ left:0,right:25,top:6,bottom:0 }} accessibilityLayer barGap={3}>
        <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 5" strokeOpacity={.7}/>
        <XAxis type="number" domain={[0,100]} ticks={[0,25,50,75,100]} tick={{ fontSize:11,fill:'var(--text-muted)' }} tickLine={false} axisLine={false} tickFormatter={v => v + '%'}/>
        <YAxis type="category" dataKey="label" width={137} tick={{ fontSize:11,fill:'var(--text-muted)' }} tickLine={false} axisLine={false}/>
        <Tooltip cursor={{ fill:'var(--surface-muted)' }} content={<AnalyticsTooltip/>}/>
        <Bar name="Compensation" dataKey="avg_compensation_pct" fill="var(--primary)" maxBarSize={9} isAnimationActive={!reducedMotion} animationDuration={450} animationEasing="ease-out" shape={props => <DrillBar {...props} onSelect={onSelect} selected={isSelected} label={row => 'Explore compensation: ' + row.label}/>}/>
        <Bar name="Possession" dataKey="avg_possession_pct" fill="var(--slate)" maxBarSize={9} isAnimationActive={!reducedMotion} animationDuration={450} animationEasing="ease-out" animationBegin={90} shape={props => <DrillBar {...props} onSelect={onSelect} selected={isSelected} label={row => 'Explore possession: ' + row.label}/>}/>
      </BarChart></ResponsiveContainer>
    </div></div>
  </SectionCard>;
}
