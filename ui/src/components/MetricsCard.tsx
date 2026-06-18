import React from 'react';
import './MetricsCard.css';

interface Props {
  title: string;
  value: string | number;
  trend?: 'positive' | 'negative' | 'neutral';
  icon?: React.ReactNode;
}

export const MetricsCard: React.FC<Props> = ({ title, value, trend = 'neutral', icon }) => {
  return (
    <div className={`metrics-card ${trend}`}>
      <div className="metrics-card-header">
        <h3>{title}</h3>
        {icon && <div className="metrics-card-icon">{icon}</div>}
      </div>
      <div className="metrics-card-value">{value}</div>
    </div>
  );
};
