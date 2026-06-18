import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import './Chart.css';

interface Experiment {
  iteration: number;
  score: number | null;
  passed: boolean;
}

interface Props {
  experiments: Experiment[];
}

export const Chart: React.FC<Props> = ({ experiments }) => {
  const data = experiments
    .filter((e) => e.score !== null)
    .map((e) => ({
      iteration: e.iteration,
      score: e.score,
      passed: e.passed,
    }));

  if (data.length === 0) {
    return <div className="chart-empty">No data yet. Start the agent to see results.</div>;
  }

  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="iteration"
            stroke="#888"
            label={{ value: 'Iteration', position: 'insideBottom', offset: -5 }}
          />
          <YAxis
            stroke="#888"
            domain={['auto', 'auto']}
            label={{ value: 'Score', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1a1a20',
              border: '1px solid #333',
              borderRadius: '8px',
            }}
            labelStyle={{ color: '#888' }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#00ff88"
            strokeWidth={2}
            dot={{ fill: '#00ff88', strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: '#00ff88' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
