import { useState, useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import './App.css';

// Components
import Sidebar from './components/Layout/Sidebar';
import ChatPanel from './components/Chat/ChatPanel';
import FeatureGraph from './components/Graph/FeatureGraph';
import GitLabOnboardingModal from './components/Modals/GitLabOnboardingModal';
import DocumentUploadModal from './components/Modals/DocumentUploadModal';

// Types
import { Project, Citation, Message, ChatSession, GraphNode, GraphEdge } from './types';

const SEED_USER_ID = "5dc41bda-2383-4e56-8f37-661cf313163d"; 
const API_BASE = "http://localhost:8000/api";

function App() {
  const [userId] = useState<string>(() => localStorage.getItem('axis_user_id') || SEED_USER_ID);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [, setBackendHealth] = useState<'healthy' | 'offline'>('offline');
  
  const [sessions, setSessions] = useState<ChatSession[]>(() => {
    const saved = localStorage.getItem('axis_chat_sessions');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed.length > 0) return parsed;
      } catch (e) {
        console.error("Failed parsing sessions", e);
      }
    }
    return [{
      id: crypto.randomUUID(),
      title: "New Conversation",
      messages: [{
        id: 'welcome',
        role: 'model',
        content: "Welcome to **Axis AI**. Ask me anything about your project requirements or codebase.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence_score: 1.0,
        citations: []
      }]
    }];
  });

  const [activeSessionId, setActiveSessionId] = useState<string>(sessions[0]?.id || '');
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);
  const [isGitLabModalOpen, setIsGitLabModalOpen] = useState(false);
  const [isDocumentModalOpen, setIsDocumentModalOpen] = useState(false);
  const [documentProjectId, setDocumentProjectId] = useState<string>('');

  const handleNewChat = () => {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      title: "New Conversation",
      messages: [{
        id: 'welcome',
        role: 'model',
        content: "Welcome to **Axis AI**. Ask me anything about your project requirements or codebase.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence_score: 1.0,
        citations: []
      }]
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  // Graph state
  const [inspectedCitation, setInspectedCitation] = useState<Citation | null>(null);
  const [inspectedGraphData, setInspectedGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [isGraphLoading, setIsGraphLoading] = useState<boolean>(false);
  
  useEffect(() => {
    localStorage.setItem('axis_user_id', userId);
  }, [userId]);

  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem('axis_chat_sessions', JSON.stringify(sessions));
    }
  }, [sessions]);

  const fetchProjects = useCallback(async () => {
    try {
      const healthRes = await fetch(`${API_BASE}/health`);
      setBackendHealth(healthRes.ok ? 'healthy' : 'offline');
    } catch {
      setBackendHealth('offline');
    }

    try {
      const res = await fetch(`${API_BASE}/projects/?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data.projects || []);
        if (data.projects && data.projects.length > 0) {
          setActiveProject(prev => prev ?? data.projects[0]);
        }
      }
    } catch (error) {
      console.error("Failed to retrieve projects:", error);
    }
  }, [userId]);

  const handleDeleteProject = async (projectId: string) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        if (activeProject?.id === projectId) {
          setActiveProject(null);
        }
        await fetchProjects();
      } else {
        const errData = await res.json();
        alert(`Failed to delete project: ${errData.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error("Failed to delete project:", error);
      alert("Failed to delete project. Check connection to backend.");
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    const isSyncing = projects.some(p => p.connectors?.some(c => c.status === 'pending' || c.status === 'syncing'));
    if (isSyncing) {
      const interval = setInterval(() => {
        fetchProjects();
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [projects, fetchProjects]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() || isSending || !activeProject) return;

    const userText = inputMessage;
    setInputMessage('');
    setIsSending(true);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        const title = s.title.startsWith("New Conversation") 
          ? userText.substring(0, 32) + (userText.length > 32 ? "..." : "")
          : s.title;
        return { ...s, title, messages: [...s.messages, userMsg] };
      }
      return s;
    }));

    try {
      const response = await fetch(`${API_BASE}/chat/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userText,
          project_id: activeProject.id,
          session_id: activeSessionId,
          limit: 5
        })
      });

      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const data = await response.json();
      const modelMsg: Message = {
        id: crypto.randomUUID(),
        role: 'model',
        content: data.answer,
        confidence_score: data.confidence_score,
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        ragas_eval: data.ragas_eval ?? undefined,
        advanced_retrieval: data.advanced_retrieval ?? undefined,
      };

      setSessions(prev => prev.map(s => s.id === activeSessionId ? { ...s, messages: [...s.messages, modelMsg] } : s));
    } catch {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: 'model',
        content: "🚨 **Error**: Failed to reach the AI retrieval engine.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence_score: 0.0
      };
      setSessions(prev => prev.map(s => s.id === activeSessionId ? { ...s, messages: [...s.messages, errorMsg] } : s));
    } finally {
      setIsSending(false);
    }
  };

  const getPluralNodeType = (type: string | null | undefined) => {
    if (!type) return 'unknown';
    const t = type.toLowerCase().trim();
    if (t === 'feature') return 'features';
    if (t === 'requirement') return 'requirements';
    if (t === 'decision') return 'decisions';
    if (t === 'stakeholder') return 'stakeholders';
    if (t === 'event' || t === 'eventchunk') return 'events';
    return t.endsWith('s') ? t : t + 's';
  };

  const getNodeTypeColor = (type: string | null | undefined): string => {
    if (!type) return '#E0E1DD';
    const t = type.toLowerCase().trim();
    if (t === 'feature' || t === 'features') return '#FF007F';
    if (t === 'requirement' || t === 'requirements') return '#00FF66';
    if (t === 'decision' || t === 'decisions') return '#9D4EDD';
    if (t === 'stakeholder' || t === 'stakeholders') return '#FFB703';
    if (t === 'event' || t === 'events' || t === 'eventchunk') return '#E0A96D';
    return '#E0E1DD';
  };

  const fetchGraphContext = async (citation: Citation) => {
    setIsGraphLoading(true);
    setInspectedCitation(citation);
    
    const { node_id, node_type, title } = citation;
    const pluralType = getPluralNodeType(node_type);

    try {
      const res = await fetch(`${API_BASE}/graph/edges/${pluralType}/${node_id}`);
      if (!res.ok) throw new Error("Edges fetch failed");
      const edgesData = await res.json();

      const graphEdges: GraphEdge[] = [];
      const distinctNeighborsMap = new Map<string, { id: string; type: string }>();

      const strId = (val: unknown): string => typeof val === 'object' && val !== null && 'id' in val ? String((val as Record<string, unknown>).id) : String(val);

      edgesData.forEach((e: { id: string; source_id: unknown; target_id: unknown; edge_type: string; weight: number; source_type: string; target_type: string }) => {
        graphEdges.push({
          id: e.id,
          source: strId(e.source_id),
          target: strId(e.target_id),
          type: e.edge_type,
          weight: e.weight
        });

        const sId = strId(e.source_id);
        const tId = strId(e.target_id);

        if (sId !== node_id) distinctNeighborsMap.set(sId, { id: sId, type: e.source_type });
        if (tId !== node_id) distinctNeighborsMap.set(tId, { id: tId, type: e.target_type });
      });

      const neighborPromises = Array.from(distinctNeighborsMap.values()).map(async (n) => {
        try {
          const detailRes = await fetch(`${API_BASE}/graph/${getPluralNodeType(n.type)}/${n.id}`);
          if (detailRes.ok) {
            const detail = await detailRes.json();
            return { ...n, title: detail.title || detail.name || `${n.type}: ${n.id.substring(0, 8)}` };
          }
        } catch (fetchErr) {
          console.warn(`Failed to fetch neighbor detail for ${n.id}:`, fetchErr);
        }
        return { ...n, title: `${n.type}: ${n.id.substring(0, 8)}` };
      });

      const resolvedNeighbors = await Promise.all(neighborPromises);

      const centralNode: GraphNode = {
        id: node_id,
        type: node_type,
        title: title,
        x: 0, y: 0, vx: 0, vy: 0,
        radius: 26,
        color: '#00E5FF',
        isCenter: true
      };

      const nodesList: GraphNode[] = [centralNode];
      
      resolvedNeighbors.forEach((neighbor, index) => {
        nodesList.push({
          id: neighbor.id,
          type: neighbor.type,
          title: neighbor.title,
          x: 0, y: 0, vx: 0, vy: 0,
          radius: 16,
          color: getNodeTypeColor(neighbor.type),
          isCenter: false,
          angle: (index / resolvedNeighbors.length) * Math.PI * 2,
          orbitRadius: 120 + Math.random() * 20,
          orbitSpeed: 0.005 + Math.random() * 0.005
        });
      });

      setInspectedGraphData({ nodes: nodesList, edges: graphEdges });
    } catch {
      setInspectedGraphData({
        nodes: [{ id: node_id, type: node_type, title, x: 0, y: 0, vx: 0, vy: 0, radius: 26, color: '#00E5FF', isCenter: true }],
        edges: []
      });
    } finally {
      setIsGraphLoading(false);
    }
  };

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];

  return (
    <div className="app-container">
      <Sidebar 
        projects={projects}
        activeProject={activeProject}
        setActiveProject={setActiveProject}
        openGitLabModal={() => setIsGitLabModalOpen(true)}
        onDeleteProject={handleDeleteProject}
        onNewChat={handleNewChat}
        onUploadDocs={(id) => {
          setDocumentProjectId(id);
          setIsDocumentModalOpen(true);
        }}
      />

      <main className="main-content">
        <ChatPanel 
          messages={activeSession.messages}
          inputValue={inputMessage}
          setInputValue={setInputMessage}
          handleSendMessage={handleSendMessage}
          isLoading={isSending}
          onCitationClick={fetchGraphContext}
          onNewChat={handleNewChat}
        />
        
        {inspectedCitation && (
          <div className="inspector-panel">
            <div className="inspector-header">
              <div className="inspector-header-left">
                <div className="inspector-header-icon">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
                  </svg>
                </div>
                <h3>Knowledge Graph</h3>
              </div>
              <button className="inspector-close-btn" onClick={() => setInspectedCitation(null)}><X size={13} /></button>
            </div>
            <div className="inspector-body">
              <FeatureGraph 
                nodes={inspectedGraphData.nodes}
                edges={inspectedGraphData.edges}
                highlightedNodes={new Set()}
                onNodeClick={(node) => fetchGraphContext({ key: 0, node_id: node.id, node_type: node.type, title: node.title })}
                isLoading={isGraphLoading}
              />
            </div>
          </div>
        )}
      </main>

      <GitLabOnboardingModal 
        isOpen={isGitLabModalOpen}
        onClose={() => setIsGitLabModalOpen(false)}
        userId={userId}
        onProjectImported={fetchProjects}
      />

      <DocumentUploadModal
        isOpen={isDocumentModalOpen}
        onClose={() => setIsDocumentModalOpen(false)}
        projectId={documentProjectId}
      />
    </div>
  );
}

export default App;
