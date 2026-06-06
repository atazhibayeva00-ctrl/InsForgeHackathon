import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import './AllocationChart.css'

const COLORS = [
  '#6366f1',
  '#22c55e',
  '#f59e0b',
  '#ef4444',
  '#06b6d4',
  '#a855f7',
  '#84cc16',
]

interface Props {
  data: Record<string, number>
  title: string
}

export function AllocationChart({ data, title }: Props) {
  const chartData = Object.entries(data)
    .filter(([, v]) => Number(v) > 0)
    .map(([name, value]) => ({ name, value: Number(value) }))

  if (chartData.length === 0) return null

  return (
    <div className="chart-card">
      {title ? <h3>{title}</h3> : null}
      <div className="chart-card-body">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={chartData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={48}
              outerRadius={78}
              paddingAngle={2}
              stroke="none"
              label={false}
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip
              formatter={(v, _name, item) => [
                `${Number(v)}%`,
                String(item.payload?.name ?? ''),
              ]}
              contentStyle={{
                background: '#1f2937',
                border: '1px solid #374151',
                borderRadius: 8,
                color: '#e5e7eb',
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="chart-legend">
        {chartData.map((entry, i) => (
          <li key={entry.name} className="chart-legend-item">
            <span
              className="chart-legend-swatch"
              style={{ background: COLORS[i % COLORS.length] }}
            />
            <span className="chart-legend-label">
              {entry.name} ({entry.value}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
