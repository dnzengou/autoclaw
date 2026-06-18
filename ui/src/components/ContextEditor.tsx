import React, { useState, useEffect } from 'react';
import { Save, RotateCcw } from 'lucide-react';
import './ContextEditor.css';

export const ContextEditor: React.FC = () => {
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchContext();
  }, []);

  const fetchContext = async () => {
    try {
      const res = await fetch('/api/context');
      const data = await res.json();
      if (data.success) {
        setContent(data.data.content);
      }
    } catch (e) {
      console.error('Failed to fetch context:', e);
    }
  };

  const saveContext = async () => {
    setSaving(true);
    try {
      await fetch('/api/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error('Failed to save context:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="context-editor">
      <div className="context-editor-header">
        <h2>Context Editor</h2>
        <div className="context-editor-actions">
          <button onClick={fetchContext} disabled={saving}>
            <RotateCcw size={16} /> Reload
          </button>
          <button
            className="btn-primary"
            onClick={saveContext}
            disabled={saving}
          >
            <Save size={16} /> {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="# AUTOCALW CONTEXT\n\n## MISSION\n..."
        spellCheck={false}
      />
      <div className="context-editor-help">
        <h3>Quick Reference</h3>
        <ul>
          <li><strong>MISSION</strong> - What we're building</li>
          <li><strong>CONSTRAINTS</strong> - Rules and limits</li>
          <li><strong>HYPOTHESIS QUEUE</strong> - What to try next</li>
          <li><strong>LEARNINGS</strong> - AI appends here automatically</li>
        </ul>
      </div>
    </div>
  );
};
