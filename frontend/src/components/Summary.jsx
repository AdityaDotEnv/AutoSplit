import React, {useEffect, useState} from 'react';
import API from '../api';
import {PieChart, Pie, Cell, Tooltip, Legend} from 'recharts';

export default function Summary({group}){
  const [data, setData] = useState(null);

  useEffect(()=>{
    async function load(){ 
      const res = await API.get(`/group/${group.id}/summary`);
      setData(res.data);
    }
    load();
  }, [group]);

  if(!data) return <div>Loading summary...</div>;

  const pieData = data.members.map(m => ({name: m.name, value: Math.round(m.total_owed*100)/100}));

  return (
    <div style={{marginTop:20}}>
      <h3>Monthly Summary</h3>
      <p>Active bills: {data.bill_count}</p>
      <PieChart width={400} height={300}>
        <Pie dataKey="value" data={pieData} outerRadius={100} label />
        <Tooltip />
      </PieChart>

      <h4>Who owes what</h4>
      <ul>
        {data.members.map(m => <li key={m.id}>{m.name}: ₹{m.total_owed.toFixed(2)} — <PayButtons member={m} /></li>)}
      </ul>
    </div>
  );
}

function PayButtons({member}){
  async function payViaUPI(){
    const res = await fetch('http://localhost:5000/api/pay/upi', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({upi: member.upi_id || 'example@upi', name:member.name, amount: member.total_owed})
    });
    const d = await res.json();
    window.open(d.upi_link, '_blank');
  }
  async function payViaVenmo(){
    const res = await fetch('http://localhost:5000/api/pay/venmo', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({venmo_id: member.venmo_id || 'venmo_user', amount: member.total_owed})
    });
    const d = await res.json();
    window.open(d.venmo_link, '_blank');
  }
  return (
    <span>
      <button onClick={payViaUPI}>Pay UPI</button>
      <button onClick={payViaVenmo}>Pay Venmo</button>
    </span>
  )
}
