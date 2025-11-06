import React, {useState} from 'react';
import API from '../api';
import AssignItems from './AssignItems';

export default function Upload({group}){
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);

  async function upload(){
    if(!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('group_id', group.id);
    const res = await API.post('/upload', form, { headers: {'Content-Type':'multipart/form-data'} });
    setResult(res.data);
  }

  return (
    <div style={{marginTop:20, border:'1px solid #ddd', padding:12, maxWidth:800}}>
      <h3>Upload a bill (screenshot or scan)</h3>
      <input type="file" accept="image/*,application/pdf" onChange={e=>setFile(e.target.files[0])} />
      <button onClick={upload}>Upload & Parse</button>

      {result && (
        <div style={{marginTop:16}}>
          <h4>Detected Items</h4>
          <ul>
            {result.items.map(it=>(
              <li key={it.id}>{it.description} — ₹{it.price.toFixed(2)}</li>
            ))}
          </ul>
          <AssignItems group={group} bill={result} />
        </div>
      )}
    </div>
  )
}
