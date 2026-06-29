import { useState, useEffect, useCallback } from 'react';
import { Play, Square, RotateCcw, GitBranch, TrendingUp, Clock, Activity } from 'lucide-react';
import { MetricsCard } from './components/MetricsCard';
import { ExperimentList } from './components/ExperimentList';
import { ContextEditor } from './components/ContextEditor';
import { Chart } from './components/Chart';
import { useWebSocket } from './hooks/useWebSocket';
import './App.css';

interface Metrics {
  experiments_total: number;
  experiments_successful: number;
  experiments_failed: number;
  best_score: number | null;
  current_iteration: number;
}

interface Experiment {
  id: string;
  iteration: number;
  hypothesis: string;
  score: number | null;
  passed: boolean;
  timestamp: string;
  duration_ms: number;
}

function App() {
  const [metrics, setMetrics] = useState<Metrics>({
    experiments_total: 0,
    experiments_successful: 0,
    experiments_failed: 0,
    best_score: null,
    current_iteration: 0,
  });
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'context' | 'experiments'>('dashboard');

  const { lastMessage, sendMessage } = useWebSocket('ws://localhost:8080/ws');

  useEffect(() => {
    if (lastMessage) {
      const data = JSON.parse(lastMessage.data);
      if (data.type === 'metrics_update' || data.type === 'init') {
        setMetrics(data.data);
      }
    }
  }, [lastMessage]);

  useEffect(() => {
    fetchExperiments();
    const interval = setInterval(fetchExperiments, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchExperiments = async () => {
    try {
      const res = await fetch('/api/experiments');
      const data = await res.json();
      if (data.success) {
        setExperiments(data.data);
      }
    } catch (e) {
      console.error('Failed to fetch experiments:', e);
    }
  };

  const startAgent = async () => {
    try {
      await fetch('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      setIsRunning(true);
    } catch (e) {
      console.error('Failed to start agent:', e);
    }
  };

  const stopAgent = async () => {
    try {
      await fetch('/api/stop', { method: 'POST' });
      setIsRunning(false);
    } catch (e) {
      console.error('Failed to stop agent:', e);
    }
  };

  const successRate = metrics.experiments_total > 0
    ? ((metrics.experiments_successful / metrics.experiments_total) * 100).toFixed(1)
    : '0';

  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <GitBranch className="logo-icon" />
          <h1>Autoclaw</h1>
        </div>
        <div className="status">
          <span className={`status-dot ${isRunning ? 'running' : ''}`} />
          <span>{isRunning ? 'Running' : 'Idle'}</span>
        </div>
      </header>

      <nav className="nav">
        <button
          className={activeTab === 'dashboard' ? 'active' : ''}
          onClick={() => setActiveTab('dashboard')}
        >
          <Activity size={18} /> Dashboard
        </button>
        <button
          className={activeTab === 'context' ? 'active' : ''}
          onClick={() => setActiveTab('context')}
        >
          <GitBranch size={18} /> Context
        </button>
        <button
          className={activeTab === 'experiments' ? 'active' : ''}
          onClick={() => setActiveTab('experiments')}
        >
          <TrendingUp size={18} /> Experiments
        </button>
      </nav>

      <main className="main">
        {activeTab === 'dashboard' && (
          <>
            <div className="controls">
              <button
                className="btn-primary"
                onClick={startAgent}
                disabled={isRunning}
              >
                <Play size={18} /> Start
              </button>
              <button
                className="btn-danger"
                onClick={stopAgent}
                disabled={!isRunning}
              >
                <Square size={18} /> Stop
              </button>
              <button className="btn-secondary">
                <RotateCcw size={18} /> Reset
              </button>
            </div>

            <div className="metrics-grid">
              <MetricsCard
                title="Total Experiments"
                value={metrics.experiments_total}
                icon={<Activity size={24} />}
              />
              <MetricsCard
                title="Success Rate"
                value={`${successRate}%`}
                trend={parseFloat(successRate) > 50 ? 'positive' : 'negative'}
                icon={<TrendingUp size={24} />}
              />
              <MetricsCard
                title="Best Score"
                value={metrics.best_score?.toFixed(4) || '-'}
                trend="positive"
                icon={<TrendingUp size={24} />}
              />
              <MetricsCard
                title="Current Iteration"
                value={metrics.current_iteration}
                icon={<Clock size={24} />}
              />
            </div>

            <div className="chart-section">
              <h2>Score History</h2>
              <Chart experiments={experiments} />
            </div>

            <div className="recent-experiments">
              <h2>Recent Experiments</h2>
              <ExperimentList experiments={experiments.slice(0, 5)} />
            </div>
          </>
        )}

        {activeTab === 'context' && <ContextEditor />}

        {activeTab === 'experiments' && (
          <div className="experiments-page">
            <h2>All Experiments</h2>
            <ExperimentList experiments={experiments} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
