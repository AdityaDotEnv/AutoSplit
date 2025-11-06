import React, { useState, useRef } from "react";
import axios from "axios";
import AssignItems from "./AssignItems";
import Summary from "./Summary";

export default function Upload({ group }) {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadAreaClick = () => {
    fileInputRef.current?.click();
  };

  async function upload() {
    if (!file) {
      setError("Please select a file first!");
      return;
    }
    setLoading(true);
    setError("");

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("group_id", group?.id || 1);

      const res = await axios.post("http://localhost:5000/api/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        withCredentials: false,
      });

      setResult(res.data);
    } catch (err) {
      console.error("Upload failed:", err);
      setError("Upload failed. Please check your backend connection.");
    } finally {
      setLoading(false);
    }
  }

  const handleSaved = () => setRefreshToken((n) => n + 1);

  return (
    <div className="upload-card">
      <div className="card-header">
        <h3>Upload Bill</h3>
        <p>Upload a screenshot or scan of your bill</p>
      </div>

      <div 
        className={`upload-area ${dragActive ? 'drag-active' : ''} ${file ? 'file-selected' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={handleUploadAreaClick}
      >
        <div className="upload-content">
          <div className="upload-icon">📄</div>
          <div className="upload-text">
            {file ? (
              <>
                <strong>Selected file:</strong>
                <p>{file.name}</p>
              </>
            ) : (
              <>
                <strong>Drag & drop your bill</strong>
                <p>or click to browse files</p>
                <span className="file-types">Supports: JPG, PNG, PDF</span>
              </>
            )}
          </div>
        </div>
        
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,application/pdf"
          onChange={handleFileSelect}
          className="file-input-hidden"
        />
      </div>

      {file && (
        <div className="file-preview">
          <div className="file-info">
            <span className="file-name">{file.name}</span>
            <button 
              className="clear-file-btn"
              onClick={() => setFile(null)}
            >
              ×
            </button>
          </div>
        </div>
      )}

      <button
        onClick={upload}
        disabled={loading || !file}
        className="upload-btn"
      >
        {loading ? (
          <>
            <div className="spinner"></div>
            Processing...
          </>
        ) : (
          <>
            <span>⚡</span>
            Upload & Parse Bill
          </>
        )}
      </button>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="results-section">
          <div className="results-header">
            <h4>Detected Items</h4>
            <span className="items-count">{result.items.length} items</span>
          </div>
          
          <div className="items-list">
            {result.items.map((it) => (
              <div key={it.id} className="item-card">
                <div className="item-description">{it.description}</div>
                <div className="item-price">₹{it.price.toFixed(2)}</div>
              </div>
            ))}
          </div>

          <AssignItems group={group} bill={result} onSaved={handleSaved} />
        </div>
      )}
    </div>
  );
}