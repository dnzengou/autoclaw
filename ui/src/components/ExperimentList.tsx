import React from 'react';
import { CheckCircle, XCircle } from 'lucide-react';
import './ExperimentList.css';

interface Experiment {
  id: string;
  iteration: number;
  hypothesis: string;
  score: number | null;
  passed: boolean;
  timestamp: string;
  duration_ms: number;
}

interface Props {
  experiments: Experiment[];
}

export const ExperimentList: React.FC<Props> = ({ experiments }) => {
  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <div className="experiment-list">
      <table>
        <thead>
          <tr>
            <th>Iter</th>
            <th>Hypothesis</th>
            <th>Score</th>
            <th>Duration</th>
            <th>Time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {experiments.map((exp) => (
            <tr key={exp.id} className={exp.passed ? 'passed' : 'failed'}>
              <td>{exp.iteration}</td>
              <td className="hypothesis" title={exp.hypothesis}>
                {exp.hypothesis.length > 50
                  ? exp.hypothesis.substring(0, 50) + '...'
                  : exp.hypothesis}
              </td>
              <td>{exp.score?.toFixed(4) || '-'}</td>
              <td>{formatDuration(exp.duration_ms)}</td>
              <td>{formatTime(exp.timestamp)}</td>
              <td>
                {exp.passed ? (
                  <span className="badge success">
                    <CheckCircle size={14} /> Pass
                  </span>
                ) : (
                  <span className="badge fail">
                    <XCircle size={14} /> Fail
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
