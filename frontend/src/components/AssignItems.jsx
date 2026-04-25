import React, { useState, useEffect } from "react";
import API from "../api";

export default function AssignItems({ group, bill, onSaved }) {
  const [members, setMembers] = useState([]);
  const [assignMap, setAssignMap] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadMembers() {
      try {
        const res = await API.get(`/groups/${group.id}`);
        setMembers(res.data.members || []);
      } catch (e) {
        console.error("Failed to load members:", e);
        setError("Failed to load members.");
      }
    }
    if (group?.id) loadMembers();
  }, [group]);

  function toggleAssign(itemId, memberId) {
    const cur = assignMap[itemId] || [];
    const exists = cur.includes(memberId);
    setAssignMap({
      ...assignMap,
      [itemId]: exists ? cur.filter((m) => m !== memberId) : [...cur, memberId],
    });
  }

  async function saveAssignments() {
    try {
      setSaving(true);
      setError("");

      const payload = [];
      for (const it of bill.items) {
        const assigned = assignMap[it.id] || [];
        if ((assigned?.length || 0) === 0) {
          const allIds = (members || []).map((m) => m.id);
          if (allIds.length > 0) {
            const share = Number(it.price) / allIds.length;
            for (const mid of allIds) {
              payload.push({ item_id: it.id, member_id: mid, share });
            }
          }
        } else {
          const share = Number(it.price) / assigned.length;
          for (const mid of assigned) {
            payload.push({ item_id: it.id, member_id: mid, share });
          }
        }
      }

      await API.post("/assign", { assignments: payload });
      onSaved?.();

      window.dispatchEvent(
        new CustomEvent("autosplit:assignmentsSaved", {
          detail: { groupId: group.id },
        })
      );
    } catch (e) {
      console.error("Save failed:", e);
      setError("Failed to save assignments. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const assignedTotal = bill.items.reduce((acc, it) => {
    const assigned = assignMap[it.id] || [];
    return assigned.length > 0 ? acc + Number(it.price) : acc;
  }, 0);
  const totalBill = bill.items.reduce((acc, it) => acc + Number(it.price), 0);

  return (
    <div className="assign-items-section">
      <div className="section-header">
        <h4>Assign Items to People</h4>
        <div className="assignment-help">
          Click to assign items to group members
        </div>
      </div>
      
      {error && <div className="error-message">{error}</div>}

      <div className="assignment-grid">
        <div className="assignment-header">
          <div className="item-col">Item</div>
          <div className="price-col">Price</div>
          <div className="assign-col">Assign To</div>
        </div>
        
        <div className="assignment-body">
          {bill.items.map((it) => (
            <div key={it.id} className="assignment-row">
              <div className="item-col" title={it.description}>
                {it.description}
              </div>
              <div className="price-col">
                ₹{Number(it.price).toFixed(2)}
              </div>
              <div className="assign-col">
                {members.map((m) => {
                  const checked = (assignMap[it.id] || []).includes(m.id);
                  return (
                    <label 
                      key={m.id} 
                      className={`checkbox-label ${checked ? 'checked' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAssign(it.id, m.id)}
                        className="checkbox-input"
                      />
                      <span>{m.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="assignment-summary-row">
          <div className="item-col">Assigned Subtotal</div>
          <div className="price-col">₹{assignedTotal.toFixed(2)}</div>
          <div className="assign-col">
            <span className="summary-info">
              {assignedTotal === totalBill 
                ? "✅ All items assigned" 
                : `Remaining: ₹${(totalBill - assignedTotal).toFixed(2)}`}
            </span>
          </div>
        </div>
      </div>

      <button
        onClick={saveAssignments}
        disabled={saving}
        className="save-assignments-btn"
      >
        {saving ? (
          <>
            <div className="spinner small"></div>
            Saving Assignments...
          </>
        ) : (
          <>
            <span>💾</span>
            Save Assignments
          </>
        )}
      </button>
    </div>
  );
}