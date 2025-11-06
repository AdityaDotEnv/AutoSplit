import React, { useEffect, useState, useRef } from "react";
import API from "../api";
import { ResponsiveContainer, PieChart, Pie, Tooltip, Legend, Cell } from "recharts";

const COLORS = [
  "#6366F1", "#22C55E", "#F97316", "#06B6D4", "#E11D48",
  "#84CC16", "#A855F7", "#F59E0B", "#10B981", "#3B82F6"
];

export default function Summary({ group, refreshToken = 0 }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const timeoutRef = useRef(null);

  async function load() {
    if (!group?.id) return;
    try {
      const res = await API.get(`/group/${group.id}/summary`);
      setData(res.data);
      setErr("");
    } catch (e) {
      console.error(e);
      setErr("Failed to load summary");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [group, refreshToken]);

  useEffect(() => {
    function onSaved(e) {
      const currentId = String(group?.id ?? "");
      const eventId = String(e?.detail?.groupId ?? "");
      if (currentId && eventId && currentId === eventId) {
        load();
        clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(load, 200);
      }
    }
    window.addEventListener("autosplit:assignmentsSaved", onSaved);
    return () => {
      window.removeEventListener("autosplit:assignmentsSaved", onSaved);
      clearTimeout(timeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [String(group?.id ?? "")]);

  useEffect(() => {
    function onFocus() {
      load();
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [String(group?.id ?? "")]);

  if (err) return <div className="error-message">{err}</div>;
  if (!data) return <div className="loading-state">Loading summary...</div>;

  const pieData = (data.members || [])
    .map((m) => ({
      name: m.name,
      value: Math.max(0, Math.round((m.total_owed || 0) * 100) / 100),
    }))
    .filter((d) => d.value > 0);

  const totalOwed = data.members?.reduce((sum, m) => sum + (m.total_owed || 0), 0) || 0;

  return (
    <div className="summary-card">
      <div className="card-header">
        <h3>Expense Summary</h3>
        <div className="summary-stats">
          <div className="stat">
            <div className="stat-label">Active Bills</div>
            <div className="stat-value">{data.bill_count}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Total Owed</div>
            <div className="stat-value">₹{totalOwed.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {pieData.length > 0 ? (
        <div className="chart-section">
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  outerRadius={110}
                  label={({ name, value }) => `${name}: ₹${value}`}
                  isAnimationActive={true}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${entry.name}-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value) => [`₹${value}`, 'Amount']}
                  contentStyle={{
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                  }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon">📊</div>
          <h4>No expenses yet</h4>
          <p>Upload and assign bills to see the summary</p>
        </div>
      )}

      <div className="breakdown-section">
        <h4>Balance Breakdown</h4>
        <div className="members-list">
          {data.members.map((m) => (
            <div key={m.id} className="member-balance">
              <div className="member-info">
                <div 
                  className="member-color"
                  style={{ 
                    backgroundColor: COLORS[data.members.indexOf(m) % COLORS.length] 
                  }}
                ></div>
                <span className="member-name">{m.name}</span>
              </div>
              <div className={`balance-amount ${m.total_owed > 0 ? 'owed' : 'zero'}`}>
                ₹{Number(m.total_owed || 0).toFixed(2)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}