import React, {useEffect, useState} from 'react';
import io from 'socket.io-client';
const socket = io('http://localhost:5000');

export default function Chat({group, user}){
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');

  useEffect(() => {
    socket.emit('join', {group: group.id, user});
    socket.on('message', (m) => setMessages(prev => [...prev, m]));
    socket.on('system', (m) => setMessages(prev => [...prev, {system: true, ...m}]));
    return () => { 
      socket.off('message'); 
      socket.off('system'); 
    }
  }, [group]);

  function send(){
    if (text.trim()) {
      socket.emit('message', {group: group.id, user, text});
      setText('');
    }
  }

  function handleKeyPress(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-card">
      <div className="chat-header">
        <h4>Group Chat</h4>
        <div className="online-indicator">
          <div className="indicator-dot"></div>
          Live
        </div>
      </div>
      
      <div className="messages-container">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.system ? 'system' : ''}`}>
            {m.system ? (
              <div className="system-message">
                <span className="system-icon">⚡</span>
                {m.msg}
              </div>
            ) : (
              <div className="user-message">
                <div className="message-sender">{m.user}:</div>
                <div className="message-text">{m.text}</div>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="chat-input-container">
        <input 
          value={text} 
          onChange={e => setText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type a message..." 
          className="chat-input"
        />
        <button 
          onClick={send} 
          disabled={!text.trim()}
          className="send-button"
        >
          <span>↑</span>
        </button>
      </div>
    </div>
  );
}