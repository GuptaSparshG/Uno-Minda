import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLORS = {
  primary: "#2f80ed",
  primaryInk: "#1d4ed8",
  teal: "#10b981",
  amber: "#f59e0b",
  violet: "#8b5cf6",
  ink: "#94a3b8",
  grid: "#e6eaf1",
};

export function QualityTrend({
  data,
}: {
  data: { section: string; score: number }[];
}) {
  return (
    <div className="h-48">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="qline" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.primary} stopOpacity={0.25} />
              <stop offset="100%" stopColor={COLORS.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={COLORS.grid}
            vertical={false}
          />
          <XAxis
            dataKey="section"
            axisLine={false}
            tickLine={false}
            fontSize={10}
            stroke={COLORS.ink}
            interval="preserveStartEnd"
            tickFormatter={(s: string) =>
              s.length > 8 ? `${s.slice(0, 8)}…` : s
            }
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            fontSize={10}
            stroke={COLORS.ink}
            domain={[0, 100]}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 10,
              border: "1px solid #e6eaf1",
              fontSize: 12,
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke={COLORS.primary}
            strokeWidth={2.5}
            dot={{ r: 3, fill: COLORS.primary, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: COLORS.primary }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ViolationsBars({
  data,
}: {
  data: { rule: string; count: number }[];
}) {
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
          barCategoryGap="30%"
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={COLORS.grid}
            vertical={false}
          />
          <XAxis
            dataKey="rule"
            axisLine={false}
            tickLine={false}
            fontSize={11}
            stroke={COLORS.ink}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            fontSize={10}
            stroke={COLORS.ink}
          />
          <Tooltip
            cursor={{ fill: "rgba(15,23,42,0.04)" }}
            contentStyle={{
              borderRadius: 10,
              border: "1px solid #e6eaf1",
              fontSize: 12,
            }}
          />
          <Bar dataKey="count" radius={[8, 8, 0, 0]}>
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={d.count === max ? COLORS.primary : "#bcd3f7"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ClassificationArea({
  data,
}: {
  data: { name: string; value: number }[];
}) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="cls" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.primary} stopOpacity={0.35} />
              <stop offset="100%" stopColor={COLORS.primary} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={COLORS.grid}
            vertical={false}
          />
          <XAxis
            dataKey="name"
            axisLine={false}
            tickLine={false}
            fontSize={11}
            stroke={COLORS.ink}
          />
          <YAxis hide />
          <Tooltip
            contentStyle={{
              borderRadius: 10,
              border: "1px solid #e6eaf1",
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={COLORS.primary}
            strokeWidth={2}
            fill="url(#cls)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
