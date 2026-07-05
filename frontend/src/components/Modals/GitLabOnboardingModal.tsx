import { useState, useEffect, useCallback } from 'react';
import { X, GitMerge, Loader2, CheckCircle2 } from 'lucide-react';

interface GitLabProject {
  id: string;
  name: string;
  name_with_namespace: string;
  description: string;
  avatar_url: string | null;
  web_url: string;
  is_connected?: boolean;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  userId: string;
  onProjectImported: () => void;
}

const API_BASE = "http://localhost:8000/api";

export default function GitLabOnboardingModal({ isOpen, onClose, userId, onProjectImported }: Props) {
  const [projects, setProjects] = useState<GitLabProject[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isImporting, setIsImporting] = useState<string | null>(null);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);
  
  const [hasGitLabToken, setHasGitLabToken] = useState<boolean | null>(null);
  const [tokenInput, setTokenInput] = useState('');
  const [isSavingToken, setIsSavingToken] = useState(false);

  const fetchAvailableProjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/gitlab/available?user_id=${userId}`);
      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          setHasGitLabToken(false);
          throw new Error("Invalid or expired GitLab token. Please reconnect your account by entering a new Personal Access Token.");
        }
        throw new Error("Failed to fetch GitLab projects. Ensure your account is connected.");
      }
      const data = await res.json();
      setProjects(data.projects || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to fetch projects");
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  const checkAuthAndFetch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/me?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setHasGitLabToken(data.has_gitlab);
        if (data.has_gitlab) {
          await fetchAvailableProjects();
        }
      }
    } catch {
      setError("Failed to verify authentication status.");
    } finally {
      setIsLoading(false);
    }
  }, [userId, fetchAvailableProjects]);

  useEffect(() => {
    if (isOpen && userId) {
      checkAuthAndFetch();
    }
  }, [isOpen, userId, checkAuthAndFetch]);

  const handleSaveToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setIsSavingToken(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, connector_type: 'gitlab', access_token: tokenInput.trim() })
      });
      if (!res.ok) throw new Error("Failed to save token");
      setHasGitLabToken(true);
      await fetchAvailableProjects();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save token");
    } finally {
      setIsSavingToken(false);
    }
  };

  const handleImport = async (projectId: string) => {
    setIsImporting(projectId);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/gitlab/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gitlab_project_id: projectId, user_id: userId }),
      });
      if (!res.ok) {
        throw new Error("Failed to import project.");
      }
      setImportSuccess(projectId);
      onProjectImported();
      setTimeout(() => {
        onClose();
        setImportSuccess(null);
      }, 500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setIsImporting(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel">
        <button className="modal-close" onClick={onClose}><X size={20} /></button>
        
        <div className="modal-header">
          <div className="modal-icon gitlab">
            <GitMerge size={24} />
          </div>
          <h2>Connect GitLab Project</h2>
          <p>Select a project from your GitLab account to synchronize with Axis.</p>
        </div>

        <div className="modal-body">
          {hasGitLabToken === true && !isLoading && (
            <div className="token-status-bar">
              <span className="token-status-text">Connected with Personal Access Token</span>
              <button onClick={() => { setHasGitLabToken(false); setError(null); }} className="btn-token-action">Update Token</button>
            </div>
          )}

          {error && <div className="error-banner">{error}</div>}
          
          {hasGitLabToken === false ? (
            <div className="token-setup-state">
              <p>Please enter a GitLab Personal Access Token (PAT) with <code>api</code> and <code>read_repository</code> scopes to continue.</p>
              <form onSubmit={handleSaveToken} className="token-form">
                <input
                  type="password"
                  placeholder="glpat-xxxxxxxxxxxxxxxxxxxx"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  className="token-input"
                  disabled={isSavingToken}
                />
                <button type="submit" className="btn-primary" disabled={isSavingToken || !tokenInput.trim()}>
                  {isSavingToken ? <><Loader2 className="spinner" size={16} /> Saving...</> : 'Save Token'}
                </button>
              </form>
            </div>
          ) : isLoading ? (
            <div className="loading-state">
              <Loader2 className="spinner" size={32} />
              <p>Fetching your projects...</p>
            </div>
          ) : projects.length === 0 ? (
            <div className="empty-state">
              <p>No accessible GitLab projects found.</p>
            </div>
          ) : (
            <div className="project-list">
              {projects.map(p => (
                <div key={p.id} className="project-list-item">
                  <div className="project-item-info">
                    {p.avatar_url ? (
                      <img src={p.avatar_url} alt={p.name} className="project-avatar" />
                    ) : (
                      <div className="project-avatar-placeholder">{p.name.substring(0, 2).toUpperCase()}</div>
                    )}
                    <div className="project-text">
                      <span className="project-name">{p.name_with_namespace}</span>
                      {p.description && <span className="project-desc">{p.description.substring(0, 60)}{p.description.length > 60 ? '...' : ''}</span>}
                    </div>
                  </div>
                  
                  <button 
                    className={`btn-import ${p.is_connected || importSuccess === p.id ? 'success' : ''}`}
                    onClick={() => handleImport(p.id)}
                    disabled={isImporting !== null || p.is_connected}
                  >
                    {isImporting === p.id ? (
                      <><Loader2 className="spinner" size={16} /> Importing</>
                    ) : (p.is_connected || importSuccess === p.id) ? (
                      <><CheckCircle2 size={16} /> Connected</>
                    ) : (
                      'Connect'
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
