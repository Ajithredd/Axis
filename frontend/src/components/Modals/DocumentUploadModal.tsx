import React, { useState, useRef } from 'react';
import { X, UploadCloud, File, CheckCircle, AlertCircle, Loader2, Sparkles } from 'lucide-react';

const API_BASE = "http://localhost:8000/api";

interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}

export default function DocumentUploadModal({ isOpen, onClose, projectId }: DocumentUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(false);
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      // Check size (10MB limit)
      if (selectedFile.size > 10 * 1024 * 1024) {
        setError('File exceeds the 10MB limit.');
        setFile(null);
        return;
      }
      setFile(selectedFile);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setSuccess(false);

    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to upload document');
      }

      setSuccess(true);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      // Auto close after 2 seconds
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 2000);
      
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'An error occurred during upload');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel document-upload-modal" style={{ maxWidth: '520px', padding: 0, overflow: 'hidden' }}>
        <div className="modal-header-premium">
          <div className="header-icon-bg">
            <UploadCloud size={20} className="header-icon" />
          </div>
          <div className="header-text">
            <h3>Project Context</h3>
            <p>Upload files to teach Axis about this project</p>
          </div>
          <button className="icon-btn close-btn" onClick={onClose} disabled={isUploading}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body" style={{ padding: '24px' }}>
          <div 
            className={`upload-dropzone-premium ${isUploading ? 'disabled' : ''}`}
            onClick={() => !isUploading && fileInputRef.current?.click()}
          >
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              style={{ display: 'none' }} 
              accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf"
              disabled={isUploading}
            />
            
            <div className="dropzone-glow"></div>

            {file ? (
              <div className="file-preview-state">
                <div className="file-icon-wrapper">
                  <File size={32} color="var(--primary)" />
                  <div className="success-badge"><CheckCircle size={12} /></div>
                </div>
                <div className="file-info">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
                <button className="change-file-btn" onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}>
                  Change
                </button>
              </div>
            ) : (
              <div className="empty-upload-state">
                <div className="upload-icon-pulse">
                  <UploadCloud size={32} />
                </div>
                <h4>Select a document or drag and drop</h4>
                <p>Supports .pdf, .txt, and .md files up to 10MB</p>
                <div className="browse-btn-pseudo">Browse Files</div>
              </div>
            )}
          </div>

          {error && (
            <div className="premium-alert error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="premium-alert success">
              <Sparkles size={16} />
              <span>Document successfully uploaded and indexed!</span>
            </div>
          )}

          <div className="modal-actions-premium">
            <button className="btn-ghost" onClick={onClose} disabled={isUploading}>
              Cancel
            </button>
            <button 
              className={`btn-glow-primary ${!file || isUploading || success ? 'disabled' : ''}`} 
              onClick={handleUpload} 
              disabled={!file || isUploading || success}
            >
              {isUploading ? (
                <>
                  <Loader2 size={16} className="spinner" />
                  Processing...
                </>
              ) : success ? (
                <>
                  <CheckCircle size={16} />
                  Done
                </>
              ) : (
                <>
                  <UploadCloud size={16} />
                  Upload & Index
                </>
              )}
              <div className="btn-glow"></div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
