import React, {useState} from 'react';
import Upload from './components/Upload';
import GroupPage from './components/GroupPage';
import Summary from './components/Summary';
import './App.css';

export default function App(){
  const [group, setGroup] = useState(null);

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">
            <span className="title-icon">🧾</span>
            AutoSplit
          </h1>
          <p className="app-subtitle">Smart Bill & Expense Narrator</p>
        </div>
      </header>

      <main className="app-main">
        {!group && <GroupPage onCreate={g => setGroup(g)} />}
        {group && (
          <div className="group-dashboard">
            <div className="group-header">
              <div className="group-info">
                <span className="group-badge">Group</span>
                <h2 className="group-name">{group.name}</h2>
              </div>
              <button 
                className="leave-group-btn"
                onClick={() => setGroup(null)}
              >
                <span>←</span>
                Leave Group
              </button>
            </div>
            
            <div className="dashboard-grid">
              <div className="dashboard-column">
                <Upload group={group} />
              </div>
              <div className="dashboard-column">
                <Summary group={group} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}