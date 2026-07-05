import React from 'react';
import { Folder, GitMerge, Loader2, Trash2, Sparkles, Upload, GitBranch, ChevronRight } from 'lucide-react';
import { Project } from '../../types';

interface SidebarProps {
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (project: Project | null) => void;
  openGitLabModal: () => void;
  onDeleteProject: (projectId: string) => void;
  onNewChat?: () => void;
  onUploadDocs?: (projectId: string) => void;
}

export default function Sidebar({ projects, activeProject, setActiveProject, openGitLabModal, onDeleteProject, onNewChat, onUploadDocs }: SidebarProps) {
  return (
    <div className="sidebar">
      {/* Logo Header */}
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-mark">
            <div className="logo-mark-inner">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
              </svg>
            </div>
          </div>
          <div className="logo-text-group">
            <h2>Axis</h2>
            <span className="logo-sub">Alignment Engine</span>
          </div>
        </div>
      </div>

      {/* Sidebar Content */}
      <div className="sidebar-content">

        {/* Projects Section */}
        <div className="sidebar-section">
          <div className="section-label">Projects</div>
          <ul className="nav-list">
            {projects.length === 0 ? (
              <div className="sidebar-empty">
                <GitBranch size={20} style={{ margin: '0 auto 6px', opacity: 0.4, display: 'block' }} />
                <span>No projects yet</span>
              </div>
            ) : (
              projects.map(project => {
                const isSyncing = project.connectors?.some(c => c.status === 'pending' || c.status === 'syncing');
                const isActive = activeProject?.id === project.id;
                return (
                  <React.Fragment key={project.id}>
                    <li
                      className={`nav-item ${isActive ? 'active' : ''}`}
                      onClick={() => setActiveProject(project)}
                    >
                      <span className="nav-item-icon">
                        {isSyncing
                          ? <Loader2 size={15} className="spinner" />
                          : <Folder size={15} />
                        }
                      </span>
                      <span className="nav-item-label">{project.name}</span>

                      {isActive && (
                        <ChevronRight size={13} style={{ color: 'var(--purple)', flexShrink: 0, opacity: 0.7 }} />
                      )}

                      <button
                        className="delete-project-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`Delete "${project.name}" and all synced data?`)) {
                            onDeleteProject(project.id);
                          }
                        }}
                        title="Delete project"
                      >
                        <Trash2 size={13} />
                      </button>
                    </li>

                    {/* Upload docs row for active project */}
                    {isActive && onUploadDocs && (
                      <li className="upload-docs-row">
                        <button
                          className="upload-docs-btn-sidebar"
                          onClick={(e) => {
                            e.stopPropagation();
                            onUploadDocs(project.id);
                          }}
                        >
                          <Upload size={12} />
                          Upload Documents
                        </button>
                      </li>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </ul>
        </div>

      </div>

      {/* Footer Buttons */}
      <div className="sidebar-footer">
        {onNewChat && (
          <button className="sidebar-btn primary" onClick={onNewChat}>
            <Sparkles size={15} />
            New Conversation
          </button>
        )}
        <button className="sidebar-btn secondary" onClick={openGitLabModal}>
          <GitMerge size={15} />
          Connect GitLab
        </button>
      </div>
    </div>
  );
}
