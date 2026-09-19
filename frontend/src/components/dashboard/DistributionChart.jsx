import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { SectionCard } from '../common';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { DrillBar, AnalyticsTooltip } from './ChartInteraction';

export default function DistributionChart({ title,subtitle,data,onSelect,isSelected }) {
  const reducedMotion = useReducedMotion();
  return <SectionCard className="chart-panel" title={title} description={subtitle}>
    <div className="chart-scroll"><div className="chart-canvas" style={{ height: Math.max(235,data.length * 35) }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={0}><BarChart data={data} layout="vertical" margin={{ left:0,right:25,top:7,bottom:0 }} accessibilityLayer>
        <CartesianGrid strokeDasharray="3 5" horizontal={false} stroke="var(--border)" strokeOpacity={.7}/>
        <XAxis type="number" allowDecimals={false} tick={{ fontSize:11,fill:'var(--text-muted)' }} axisLine={false} tickLine={false}/>
        <YAxis type="category" dataKey="name" width={145} tick={{ fontSize:11,fill:'var(--text-muted)' }} axisLine={false} tickLine={false}/>
        <Tooltip cursor={{ fill:'var(--surface-muted)' }} content={<AnalyticsTooltip/>}/>
        <Bar dataKey="count" name="Projects" fill="var(--primary)" maxBarSize={13} isAnimationActive={!reducedMotion} animationDuration={450} animationEasing="ease-out"
          shape={props => <DrillBar {...props} onSelect={onSelect} selected={isSelected} label={row => 'Filter projects: ' + row.name}/>}/>
      </BarChart></ResponsiveContainer>
    </div></div>
    <details className="chart-data"><summary>View chart values</summary><ul>{data.map(row => <li key={row.name}><button className="chart-value-button" aria-pressed={isSelected(row)} onClick={() => onSelect(row)}><span>{row.name}</span><strong>{row.count}</strong></button></li>)}</ul></details>
  </SectionCard>;
}
