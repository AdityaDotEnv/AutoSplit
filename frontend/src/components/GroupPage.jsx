import React, {useState} from 'react';
import API from '../api';

export default function GroupPage({onCreate}){
  const [name, setName] = useState('');
  const [members, setMembers] = useState([{name:'Alice'},{name:'Bob'}]);

  function addMember(){ setMembers([...members, {name:''}]); }
  function setMemberName(i, val){ const m = [...members]; m[i].name = val; setMembers(m); }

  async function create(){
    const res = await API.post('/groups', {name, members});
    onCreate({id: res.data.id, name: res.data.name});
  }

  return (
    <div style={{border:'1px solid #ddd', padding:16, borderRadius:8, maxWidth:600}}>
      <h3>Create a Group</h3>
      <input value={name} onChange={e=>setName(e.target.value)} placeholder="Group name" />
      <h4>Members</h4>
      {members.map((m,i)=>(
        <div key={i}>
          <input placeholder="name" value={m.name} onChange={e=>setMemberName(i, e.target.value)} />
        </div>
      ))}
      <button onClick={addMember}>Add member</button>
      <div style={{marginTop:10}}>
        <button onClick={create}>Create Group</button>
      </div>
    </div>
  );
}
