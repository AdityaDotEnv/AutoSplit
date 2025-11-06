import React, {useState} from 'react';
import Upload from './components/Upload';
import GroupPage from './components/GroupPage';
import Summary from './components/Summary';

export default function App(){
  const [group, setGroup] = useState(null);

  return (
    <div style={{padding:20, fontFamily:'Inter, sans-serif'}}>
      <h1>AutoSplit — Smart Bill & Expense Narrator</h1>
      {!group && <GroupPage onCreate={g => setGroup(g)} />}
      {group && (
        <>
          <div style={{marginTop:20}}>
            <strong>Group:</strong> {group.name} <button onClick={()=>setGroup(null)}>Leave</button>
          </div>
          <Upload group={group} />
          <Summary group={group} />
        </>
      )}
    </div>
  );
}
