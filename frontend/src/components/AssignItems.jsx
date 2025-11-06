import React, {useState, useEffect} from 'react';
import API from '../api';

export default function AssignItems({group, bill}){
  const [members, setMembers] = useState([]);
  const [assignMap, setAssignMap] = useState({}); // itemId -> [memberIds]

  useEffect(()=>{
    (async ()=>{
      const res = await API.get(`/groups/${group.id}`);
      setMembers(res.data.members);
    })();
  }, [group]);

  function toggleAssign(itemId, memberId){
    const cur = assignMap[itemId] || [];
    const exists = cur.includes(memberId);
    setAssignMap({
      ...assignMap,
      [itemId]: exists ? cur.filter(m => m !== memberId) : [...cur, memberId]
    });
  }

  async function saveAssignments(){
    const payload = [];
    for(const it of bill.items){
      const assigned = assignMap[it.id] || [];
      if(assigned.length === 0){
        // by default split equally among all group members
        const equally = members.map(m => m.id);
        const share = it.price / equally.length;
        for(const mid of equally) payload.push({item_id: it.id, member_id: mid, share});
      } else {
        const share = it.price / assigned.length;
        for(const mid of assigned) payload.push({item_id: it.id, member_id: mid, share});
      }
    }
    await API.post('/assign', {assignments: payload});
    alert('Assigned!');
  }

  return (
    <div style={{marginTop:12}}>
      <h4>Assign Items to People (auto-match suggestions shown)</h4>
      <table>
        <thead><tr><th>Item</th><th>Price</th><th>Assign</th></tr></thead>
        <tbody>
          {bill.items.map(it=>(
            <tr key={it.id}>
              <td>{it.description}</td>
              <td>₹{it.price.toFixed(2)}</td>
              <td>
                {members.map(m=>(
                  <label key={m.id} style={{marginRight:8}}>
                    <input type="checkbox" onChange={()=>toggleAssign(it.id, m.id)} checked={(assignMap[it.id]||[]).includes(m.id)} />
                    {m.name}
                  </label>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={saveAssignments}>Save Assignments</button>
    </div>
  )
}
