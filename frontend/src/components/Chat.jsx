import React, { useEffect, useState } from "react";
import io from "socket.io-client";
const socket = io("http://localhost:5000");

export default function Chat({ group, user }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");

  useEffect(() => {
    socket.emit("join", { group: group.id, user });
    socket.on("message", (m) => setMessages((prev) => [...prev, m]));
    socket.on("system", (m) =>
      setMessages((prev) => [...prev, { system: true, ...m }])
    );
    return () => {
      socket.off("message");
      socket.off("system");
    };
  }, [group, user]);

  function send() {
    socket.emit("message", { group: group.id, user, text });
    setText("");
  }

  return (
    <div style={{ border: "1px solid #ddd", padding: 8, marginTop: 12 }}>
      <h4>Group Chat</h4>
      <div
        style={{
          height: 150,
          overflow: "auto",
          border: "1px solid #eee",
          padding: 8,
        }}
      >
        {messages.map((m, i) => (
          <div key={i}>
            {m.system ? <em>{m.msg}</em> : <strong>{m.user}:</strong>} {m.text}
          </div>
        ))}
      </div>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Message"
      />
      <button onClick={send}>Send</button>
    </div>
  );
}
