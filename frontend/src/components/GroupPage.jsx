import React, {useState} from 'react';
import API from '../api';

export default function GroupPage({onCreate}){
  const [name, setName] = useState('');
  const [members, setMembers] = useState([{name:'Alice'},{name:'Bob'}]);

  function addMember(){ 
    setMembers([...members, {name:''}]);
  }

  function setMemberName(i, val){ 
    const m = [...members]; 
    m[i].name = val; 
    setMembers(m); 
  }

  function removeMember(index) {
    if (members.length > 1) {
      setMembers(members.filter((_, i) => i !== index));
    }
  }

  async function create(){
    const res = await API.post('/groups', {name, members});
    onCreate({id: res.data.id, name: res.data.name});
  }

  return (
    <div className="group-creation-container">
      <div className="group-creation-card">
        <div className="creation-header">
          <h2>Create New Group</h2>
          <p>Start by creating a group and adding members</p>
        </div>

        <div className="form-group">
          <label className="form-label">Group Name</label>
          <input 
            className="form-input"
            value={name} 
            onChange={e => setName(e.target.value)} 
            placeholder="Enter group name" 
          />
        </div>

        <div className="members-section">
          <div className="section-header">
            <h3>Group Members</h3>
            <button 
              type="button"
              className="add-member-btn"
              onClick={addMember}
            >
              <span>+</span>
              Add Member
            </button>
          </div>

          <div className="members-grid">
            {members.map((m,i) => (
              <div key={i} className="member-input-group">
                <input 
                  className="member-input"
                  placeholder="Member name" 
                  value={m.name} 
                  onChange={e => setMemberName(i, e.target.value)} 
                />
                {members.length > 1 && (
                  <button
                    type="button"
                    className="remove-member-btn"
                    onClick={() => removeMember(i)}
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        <button 
          className="create-group-btn"
          onClick={create}
          disabled={!name.trim() || members.some(m => !m.name.trim())}
        >
          Create Group
          <span className="btn-arrow">→</span>
        </button>
      </div>
    </div>
  );
}