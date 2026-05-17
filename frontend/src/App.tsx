import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Send, Cpu, User, Plus, Trash2, HelpCircle, 
  RefreshCw, Database, 
  Activity, ChevronRight, Link2, Terminal, Copy, X, Award
} from 'lucide-react';
import './App.css';

// Seed User & Project fallback IDs from database
const SEED_USER_ID = "5dc41bda-2383-4e56-8f37-661cf313163d"; 
const API_BASE = "http://localhost:8000/api";

interface Project {
  id: string;
  name: string;
  description: string;
  connectors: Array<{ type: string; status: string }>;
}

interface Citation {
  key: number;
  node_id: string;
  node_type: string;
  title: string;
  url?: string | null;
  snippet?: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'model';
  content: string;
  confidence_score?: number;
  citations?: Citation[];
  timestamp: string;
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

interface GraphNode {
  id: string;
  type: string;
  title: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  isCenter: boolean;
  angle?: number;
  orbitRadius?: number;
  orbitSpeed?: number;
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}

function App() {
  // Authentication & Workspace Project State
  const [userId, setUserId] = useState<string>(() => {
    return localStorage.getItem('clarity_user_id') || SEED_USER_ID;
  });
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [backendHealth, setBackendHealth] = useState<'healthy' | 'offline'>('offline');
  
  // Multi-turn Chat Session State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [inputMessage, setInputMessage] = useState<string>('');
  const [isSending, setIsSending] = useState<boolean>(false);

  // Graph Inspection Panel State
  const [inspectedCitation, setInspectedCitation] = useState<Citation | null>(null);
  const [inspectedGraphData, setInspectedGraphData] = useState<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] });
  const [isGraphLoading, setIsGraphLoading] = useState<boolean>(false);
  const [graphHoveredNode, setGraphHoveredNode] = useState<GraphNode | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const animationFrameId = useRef<number | null>(null);

  // Persistence of User ID
  useEffect(() => {
    localStorage.setItem('clarity_user_id', userId);
  }, [userId]);

  // Fetch Health Check and Available Projects
  const fetchProjects = useCallback(async () => {
    try {
      const healthRes = await fetch(`${API_BASE}/health`);
      if (healthRes.ok) {
        setBackendHealth('healthy');
      } else {
        setBackendHealth('offline');
      }
    } catch {
      setBackendHealth('offline');
    }

    try {
      const res = await fetch(`${API_BASE}/projects/?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data.projects || []);
        if (data.projects && data.projects.length > 0) {
          // Select first project if none is active
          setSelectedProjectId(prev => prev || data.projects[0].id);
        }
      }
    } catch (error) {
      console.error("Failed to retrieve projects:", error);
    }
  }, [userId]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Load Sessions or Initialize Default Session
  useEffect(() => {
    const savedSessions = localStorage.getItem('clarity_chat_sessions');
    if (savedSessions) {
      try {
        const parsed = JSON.parse(savedSessions);
        if (parsed.length > 0) {
          setSessions(parsed);
          setActiveSessionId(parsed[0].id);
          return;
        }
      } catch (e) {
        console.error("Failed parsing sessions from storage", e);
      }
    }

    // Initialize clean session
    const defaultId = crypto.randomUUID();
    const defaultSession: ChatSession = {
      id: defaultId,
      title: "New Conversation Workspace",
      messages: [
        {
          id: 'welcome',
          role: 'model',
          content: "Welcome to **Axis AI**. I am your premium software alignment assistant.\n\nAsk me anything about your project requirements, technical decisions, event streams, or stakeholder inputs. I will search the Feature Intelligence Graph to provide highly precise answers backed by factual, inline citations.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          confidence_score: 1.0,
          citations: []
        }
      ]
    };
    setSessions([defaultSession]);
    setActiveSessionId(defaultId);
  }, []);

  // Sync Sessions to LocalStorage
  useEffect(() => {
    if (sessions.length > 0) {
      localStorage.setItem('clarity_chat_sessions', JSON.stringify(sessions));
    }
  }, [sessions]);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessions, activeSessionId, isSending]);

  // Create a new session
  const createNewSession = () => {
    const newId = crypto.randomUUID();
    const newSession: ChatSession = {
      id: newId,
      title: `Session: ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`,
      messages: [
        {
          id: crypto.randomUUID(),
          role: 'model',
          content: "A fresh environment has been prepared. State context cleared.\n\nHow can I help verify alignments in your Feature Intelligence Graph today?",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          confidence_score: 1.0,
          citations: []
        }
      ]
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveSessionId(newId);
  };

  // Delete a session
  const deleteSession = (e: React.MouseEvent, idToDelete: string) => {
    e.stopPropagation();
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== idToDelete);
      if (filtered.length === 0) {
        const fallbackId = crypto.randomUUID();
        return [{
          id: fallbackId,
          title: "New Conversation Workspace",
          messages: [{
            id: 'welcome',
            role: 'model',
            content: "Welcome to **Axis AI**. I am your premium software alignment assistant.",
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            confidence_score: 1.0,
            citations: []
          }]
        }];
      }
      return filtered;
    });
    if (activeSessionId === idToDelete) {
      setActiveSessionId(sessions.find(s => s.id !== idToDelete)?.id || '');
    }
  };

  // Clear Session History (Backend Call)
  const clearSessionHistory = async () => {
    try {
      await fetch(`${API_BASE}/chat/session/clear`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId })
      });
      setSessions(prev => prev.map(s => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            title: "Context Cleared",
            messages: [{
              id: crypto.randomUUID(),
              role: 'model',
              content: "History and multi-turn context cleared. Ask a new query to start.",
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              confidence_score: 1.0,
              citations: []
            }]
          };
        }
        return s;
      }));
    } catch (err) {
      console.error("Failed to clear session:", err);
    }
  };

  // Submit Query to Backend
  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputMessage.trim() || isSending || !selectedProjectId) return;

    const userText = inputMessage;
    setInputMessage('');
    setIsSending(true);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Update session title on the first real message
    setSessions(prev => prev.map(s => {
      if (s.id === activeSessionId) {
        const title = s.title.startsWith("New Conversation") || s.title.startsWith("Session:") 
          ? userText.substring(0, 32) + (userText.length > 32 ? "..." : "")
          : s.title;
        return {
          ...s,
          title,
          messages: [...s.messages, userMsg]
        };
      }
      return s;
    }));

    try {
      const response = await fetch(`${API_BASE}/chat/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: userText,
          project_id: selectedProjectId,
          session_id: activeSessionId,
          limit: 5
        })
      });

      if (!response.ok) {
        throw new Error(`API server returned code ${response.status}`);
      }

      const data = await response.json();
      const modelMsg: Message = {
        id: crypto.randomUUID(),
        role: 'model',
        content: data.answer,
        confidence_score: data.confidence_score,
        citations: data.citations || [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setSessions(prev => prev.map(s => {
        if (s.id === activeSessionId) {
          return {
            ...s,
            messages: [...s.messages, modelMsg]
          };
        }
        return s;
      }));

    } catch (err) {
      console.error("Chat retrieval query failure:", err);
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: 'model',
        content: "🚨 **Connection Interrupted**: I failed to reach the AI retrieval engine. Please ensure your backend server is active at `localhost:8000` and try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        confidence_score: 0.0,
        citations: []
      };
      setSessions(prev => prev.map(s => {
        if (s.id === activeSessionId) {
          return { ...s, messages: [...s.messages, errorMsg] };
        }
        return s;
      }));
    } finally {
      setIsSending(false);
    }
  };

  // Helper mapping node types to plural URL prefixes
  const getPluralNodeType = (type: string) => {
    const t = type.toLowerCase().trim();
    if (t === 'feature') return 'features';
    if (t === 'requirement') return 'requirements';
    if (t === 'decision') return 'decisions';
    if (t === 'stakeholder') return 'stakeholders';
    if (t === 'event') return 'events';
    return t.endsWith('s') ? t : t + 's';
  };

  // Fetch 1-degree BFS relationship context of an inspected node
  const fetchGraphContext = async (citation: Citation) => {
    setIsGraphLoading(true);
    setInspectedCitation(citation);
    
    const { node_id, node_type, title } = citation;
    const pluralType = getPluralNodeType(node_type);

    try {
      // 1. Fetch connected edges
      const res = await fetch(`${API_BASE}/graph/edges/${pluralType}/${node_id}`);
      if (!res.ok) throw new Error("Edges fetch failed");
      const edgesData = await res.json(); // Array of EdgeOut

      // 2. Map edges and compile distinct neighbor nodes
      const graphEdges: GraphEdge[] = [];
      const distinctNeighborsMap = new Map<string, { id: string; type: string }>();

      edgesData.forEach((e: any) => {
        graphEdges.push({
          id: e.id,
          source: strId(e.source_id),
          target: strId(e.target_id),
          type: e.edge_type,
          weight: e.weight
        });

        const sId = strId(e.source_id);
        const tId = strId(e.target_id);

        if (sId !== node_id) {
          distinctNeighborsMap.set(sId, { id: sId, type: e.source_type });
        }
        if (tId !== node_id) {
          distinctNeighborsMap.set(tId, { id: tId, type: e.target_type });
        }
      });

      // Helper to stringify UUID fields safely
      function strId(val: any): string {
        return typeof val === 'object' ? val.id || JSON.stringify(val) : String(val);
      }

      // 3. Resolve neighbor titles in parallel
      const neighborPromises = Array.from(distinctNeighborsMap.values()).map(async (n) => {
        try {
          const typePlural = getPluralNodeType(n.type);
          const detailRes = await fetch(`${API_BASE}/graph/${typePlural}/${n.id}`);
          if (detailRes.ok) {
            const detail = await detailRes.json();
            const label = detail.title || detail.display_name || detail.name || `${n.type}: ${n.id.substring(0, 8)}`;
            return { ...n, title: label };
          }
        } catch {}
        return { ...n, title: `${n.type}: ${n.id.substring(0, 8)}` };
      });

      const resolvedNeighbors = await Promise.all(neighborPromises);

      // 4. Construct high-fidelity Canvas Graph Node Structures
      const centralNode: GraphNode = {
        id: node_id,
        type: node_type,
        title: title,
        x: 0, // calculated in draw
        y: 0,
        vx: 0,
        vy: 0,
        radius: 26,
        color: '#00E5FF', // Electric cyan for inspected core
        isCenter: true
      };

      const nodesList: GraphNode[] = [centralNode];
      
      resolvedNeighbors.forEach((neighbor, index) => {
        // Distribute orbit values evenly
        const angle = (index / resolvedNeighbors.length) * Math.PI * 2;
        const orbitRadius = 120 + Math.random() * 20; // gentle variance
        const speed = 0.005 + Math.random() * 0.005; // gentle speed variance

        nodesList.push({
          id: neighbor.id,
          type: neighbor.type,
          title: neighbor.title,
          x: 0,
          y: 0,
          vx: 0,
          vy: 0,
          radius: 16,
          color: getNodeTypeColor(neighbor.type),
          isCenter: false,
          angle,
          orbitRadius,
          orbitSpeed: speed
        });
      });

      setInspectedGraphData({ nodes: nodesList, edges: graphEdges });

    } catch (e) {
      console.error("Failed to construct graph node inspection context", e);
      // Fallback: simple central node with zero neighbors
      setInspectedGraphData({
        nodes: [{
          id: node_id,
          type: node_type,
          title: title,
          x: 0,
          y: 0,
          vx: 0,
          vy: 0,
          radius: 26,
          color: '#00E5FF',
          isCenter: true
        }],
        edges: []
      });
    } finally {
      setIsGraphLoading(false);
    }
  };

  const getNodeTypeColor = (type: string): string => {
    switch (type.toLowerCase()) {
      case 'feature': return '#FF007F'; // Vibrant Pink
      case 'requirement': return '#00FF66'; // Lime neon success
      case 'decision': return '#9D4EDD'; // Electric purple
      case 'stakeholder': return '#FFB703'; // Amber gold
      case 'event': return '#E0A96D'; // Bronze copper
      default: return '#E0E1DD';
    }
  };

  // HTML5 canvas drawing loop with interactive orbiting nodes & glowing visual flows
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let localWidth = canvas.clientWidth;
    let localHeight = canvas.clientHeight;
    
    // Set matching buffer resolutions
    if (canvas.width !== localWidth || canvas.height !== localHeight) {
      canvas.width = localWidth;
      canvas.height = localHeight;
    }

    const { nodes, edges } = inspectedGraphData;

    // Particle trace array to simulate alignment flows
    const particleFlows: Array<{ edgeId: string; progress: number; speed: number }> = [];
    edges.forEach(e => {
      particleFlows.push({
        edgeId: e.id,
        progress: Math.random(),
        speed: 0.008 + Math.random() * 0.005
      });
    });

    const renderLoop = () => {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;

      // Update positions
      nodes.forEach(n => {
        if (n.isCenter) {
          n.x = centerX;
          n.y = centerY;
        } else if (n.angle !== undefined && n.orbitRadius !== undefined && n.orbitSpeed !== undefined) {
          n.angle += n.orbitSpeed; // Incremental rotation
          n.x = centerX + n.orbitRadius * Math.cos(n.angle);
          n.y = centerY + n.orbitRadius * Math.sin(n.angle);
        }
      });

      // 1. Draw Edges
      edges.forEach((e, idx) => {
        const sourceNode = nodes.find(n => n.id === e.source);
        const targetNode = nodes.find(n => n.id === e.target);
        if (!sourceNode || !targetNode) return;

        // Draw dotted glow line
        ctx.beginPath();
        ctx.moveTo(sourceNode.x, sourceNode.y);
        ctx.lineTo(targetNode.x, targetNode.y);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Animate glowing connection particle flow
        const flow = particleFlows[idx];
        if (flow) {
          flow.progress += flow.speed;
          if (flow.progress > 1) flow.progress = 0;

          const px = sourceNode.x + (targetNode.x - sourceNode.x) * flow.progress;
          const py = sourceNode.y + (targetNode.y - sourceNode.y) * flow.progress;

          ctx.beginPath();
          ctx.arc(px, py, 3.5, 0, Math.PI * 2);
          ctx.fillStyle = '#00E5FF';
          ctx.shadowBlur = 8;
          ctx.shadowColor = '#00E5FF';
          ctx.fill();
          ctx.shadowBlur = 0; // reset
        }
      });

      // 2. Draw Nodes
      nodes.forEach(n => {
        ctx.save();
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        
        // Add ambient glow if central node or hovered
        const isHovered = graphHoveredNode?.id === n.id;
        if (n.isCenter || isHovered) {
          ctx.shadowBlur = isHovered ? 20 : 15;
          ctx.shadowColor = n.color;
        }

        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.restore();

        // Draw node type border
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw shortened text label underneath the node
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
        ctx.font = n.isCenter ? '500 11px var(--font-sans)' : '400 9px var(--font-sans)';
        ctx.textAlign = 'center';
        
        let label = n.title;
        if (label.length > 18) label = label.substring(0, 15) + '...';
        ctx.fillText(label, n.x, n.y + n.radius + 14);

        // Sublabel type
        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
        ctx.font = '500 7.5px var(--font-sans)';
        ctx.fillText(n.type.toUpperCase(), n.x, n.y + n.radius + 23);
      });

      animationFrameId.current = requestAnimationFrame(renderLoop);
    };

    renderLoop();

    return () => {
      if (animationFrameId.current) {
        cancelAnimationFrame(animationFrameId.current);
      }
    };
  }, [inspectedGraphData, graphHoveredNode]);

  // Handle canvas mouse moves for custom interactivity
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const hovered = inspectedGraphData.nodes.find(n => {
      const dx = n.x - x;
      const dy = n.y - y;
      return Math.sqrt(dx * dx + dy * dy) < n.radius + 5;
    });

    setGraphHoveredNode(hovered || null);
    canvas.style.cursor = hovered ? 'pointer' : 'default';
  };

  // Canvas click to traverse deep into the graph
  const handleCanvasClick = () => {
    if (graphHoveredNode) {
      // inspect clicked node
      fetchGraphContext({
        key: 0,
        node_id: graphHoveredNode.id,
        node_type: graphHoveredNode.type,
        title: graphHoveredNode.title
      });
    }
  };

  // Custom Inline Tokenizer to safely parse Bold, Inline Code, and dynamic interactive Citation badges
  const parseInlineElements = (text: string, citations?: Citation[]): React.ReactNode[] => {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    
    // Pattern to match citations [1], [2], bold **text**, and inline `code`
    const regex = /(\[(\d+)\]|\*\*([^*]+)\*\*|`([^`]+)`)/g;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const precedingText = text.substring(lastIndex, match.index);
      if (precedingText) {
        parts.push(precedingText);
      }

      if (match[2]) {
        // Citation match
        const keyNum = parseInt(match[2], 10);
        const citation = citations?.find(c => c.key === keyNum);
        
        parts.push(
          <button
            key={`citation-${match.index}`}
            className={`cit-badge ${citation ? 'resolved' : ''}`}
            onClick={() => citation && fetchGraphContext(citation)}
            title={citation ? `${citation.node_type}: ${citation.title}` : `Citation [${keyNum}]`}
          >
            [{keyNum}]
          </button>
        );
      } else if (match[3]) {
        // Bold match
        parts.push(<strong key={`bold-${match.index}`}>{match[3]}</strong>);
      } else if (match[4]) {
        // Inline code match
        parts.push(<code key={`code-${match.index}`} className="inline-code">{match[4]}</code>);
      }

      lastIndex = regex.lastIndex;
    }

    const remainingText = text.substring(lastIndex);
    if (remainingText) {
      parts.push(remainingText);
    }

    return parts;
  };

  // Formats multi-line RAG outputs (paragraphs, bullet lists, code blocks) safely
  const formatMarkdown = (content: string, citations?: Citation[]): React.ReactNode => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    
    let inCodeBlock = false;
    let codeContent: string[] = [];
    let codeLanguage = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Code Block entry/exit
      if (line.trim().startsWith('```')) {
        if (!inCodeBlock) {
          inCodeBlock = true;
          codeLanguage = line.trim().substring(3) || 'javascript';
          codeContent = [];
        } else {
          inCodeBlock = false;
          elements.push(
            <pre key={`codeblock-${i}`} className="code-block-container">
              <div className="code-header">
                <span>{codeLanguage.toUpperCase()}</span>
                <button 
                  onClick={() => navigator.clipboard.writeText(codeContent.join('\n'))}
                  className="code-copy-btn"
                >
                  <Copy size={12} />
                  <span>Copy</span>
                </button>
              </div>
              <code>{codeContent.join('\n')}</code>
            </pre>
          );
        }
        continue;
      }

      if (inCodeBlock) {
        codeContent.push(line);
        continue;
      }

      // Headers
      if (line.startsWith('### ')) {
        elements.push(<h3 key={`h3-${i}`} className="chat-h3">{parseInlineElements(line.substring(4), citations)}</h3>);
        continue;
      }
      if (line.startsWith('## ')) {
        elements.push(<h2 key={`h2-${i}`} className="chat-h2">{parseInlineElements(line.substring(3), citations)}</h2>);
        continue;
      }
      if (line.startsWith('# ')) {
        elements.push(<h1 key={`h1-${i}`} className="chat-h1">{parseInlineElements(line.substring(2), citations)}</h1>);
        continue;
      }

      // Lists
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        elements.push(
          <li key={`li-${i}`} className="chat-li">
            {parseInlineElements(line.trim().substring(2), citations)}
          </li>
        );
        continue;
      }

      // Plain paragraphs
      if (line.trim() === '') {
        elements.push(<div key={`spacer-${i}`} className="paragraph-spacer" />);
      } else {
        elements.push(
          <p key={`p-${i}`} className="chat-paragraph">
            {parseInlineElements(line, citations)}
          </p>
        );
      }
    }

    return <div className="markdown-content">{elements}</div>;
  };

  const activeSession = sessions.find(s => s.id === activeSessionId) || sessions[0];

  return (
    <div className="app-container">
      {/* 1. Glassmorphic Navigation Sidebar */}
      <aside className="glass-sidebar sidebar-layout">
        
        {/* Brand Indicator */}
        <div className="brand-container">
          <div className="brand-glow-circle"></div>
          <div className="brand-text-block">
            <h1 className="brand-title">AXIS AI</h1>
            <span className="brand-subtitle">ALIGNMENT SYSTEM</span>
          </div>
        </div>

        {/* Backend Health Badge */}
        <div className="health-badge-container">
          <div className={`health-dot ${backendHealth}`} />
          <span className="health-label">
            RETRIEVAL ENGINE: {backendHealth.toUpperCase()}
          </span>
        </div>

        {/* User Configuration Seed (Dynamic override supported) */}
        <div className="user-config-panel">
          <label className="config-label"><Activity size={10} /> CURRENT USER CONTEXT</label>
          <div className="config-row">
            <input 
              type="text" 
              className="user-id-input"
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value);
                setProjects([]);
              }}
              placeholder="Enter User UUID"
            />
            <button 
              className="refresh-config-btn" 
              onClick={fetchProjects} 
              title="Reload User Projects"
            >
              <RefreshCw size={12} />
            </button>
          </div>
        </div>

        {/* Workspace Project Selector */}
        <div className="project-selector-container">
          <label className="config-label"><Database size={10} /> CORE GRAPH PROJECT</label>
          <select 
            className="project-select-dropdown"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          >
            {projects.length === 0 ? (
              <option value="" disabled>No active projects found...</option>
            ) : (
              projects.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="sidebar-divider" />

        {/* Active Conversational Sessions */}
        <div className="sessions-header-row">
          <span className="sessions-title">DIALOGUE HISTORY</span>
          <button 
            className="new-session-button" 
            onClick={createNewSession}
            title="Create New Session"
          >
            <Plus size={14} />
            <span>New</span>
          </button>
        </div>

        <div className="sessions-scroll-list">
          {sessions.map(s => {
            const isActive = s.id === activeSessionId;
            return (
              <div 
                key={s.id} 
                className={`session-item ${isActive ? 'active' : ''}`}
                onClick={() => setActiveSessionId(s.id)}
              >
                <div className="session-item-left">
                  <span className="session-item-title">{s.title}</span>
                  <span className="session-item-turns">{s.messages.length} exchanges</span>
                </div>
                <button 
                  className="session-delete-btn"
                  onClick={(e) => deleteSession(e, s.id)}
                  title="Wipe Session"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            );
          })}
        </div>

        {/* Workspace footer Info */}
        <div className="sidebar-footer">
          <HelpCircle size={12} />
          <span>Semantic Integration Active</span>
        </div>
      </aside>

      {/* 2. Main Chat Arena Workspace */}
      <main className="chat-main-area">
        
        {/* Top Header Dashboard */}
        <header className="chat-top-header glass-panel">
          <div className="header-left">
            <div className="active-project-badge">
              <Database size={13} className="primary-accent" />
              <span>
                WORKSPACE: {projects.find(p => p.id === selectedProjectId)?.name || 'NONE SELECTED'}
              </span>
            </div>
          </div>
          <div className="header-right">
            <button 
              className="clear-history-button"
              onClick={clearSessionHistory}
              title="Clear current workspace turns"
            >
              <RefreshCw size={13} />
              <span>Reset Context</span>
            </button>
          </div>
        </header>

        {/* Message Thread Scroll Container */}
        <div className="chat-scroll-container">
          <div className="messages-thread">
            {activeSession.messages.map((m) => {
              const isModel = m.role === 'model';
              const showConfidence = isModel && m.confidence_score !== undefined;
              
              return (
                <div 
                  key={m.id} 
                  className={`message-box-wrapper ${m.role}`}
                >
                  <div className="message-header-row">
                    <div className="actor-profile">
                      {isModel ? (
                        <div className="avatar model"><Cpu size={14} /></div>
                      ) : (
                        <div className="avatar user"><User size={14} /></div>
                      )}
                      <span className="actor-name">
                        {isModel ? 'AXIS INTEL AGENT' : 'DEVELOPER STAKEHOLDER'}
                      </span>
                    </div>
                    <span className="message-time">{m.timestamp}</span>
                  </div>

                  <div className="message-content-container">
                    {/* Render Formatted Markdown */}
                    {formatMarkdown(m.content, m.citations)}

                    {/* Factual Confidence Banner */}
                    {showConfidence && (
                      <div className="confidence-banner">
                        <div className="confidence-left">
                          <Award size={14} className="success-accent" />
                          <span className="confidence-text">
                            Gemini Confidence Rating: <strong>{(m.confidence_score! * 100).toFixed(1)}%</strong>
                          </span>
                        </div>
                        <div className="confidence-track">
                          <div 
                            className="confidence-fill" 
                            style={{ 
                              width: `${m.confidence_score! * 100}%`,
                              backgroundColor: m.confidence_score! > 0.8 ? 'var(--success)' : 'var(--warning)'
                            }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Citations Footer List */}
                    {isModel && m.citations && m.citations.length > 0 && (
                      <div className="citations-footer">
                        <div className="citations-footer-label">
                          <Link2 size={11} />
                          <span>FACTUAL RESOURCE DIRECTORY:</span>
                        </div>
                        <div className="citations-list-grid">
                          {m.citations.map((c) => (
                            <div 
                              key={c.key} 
                              className="citation-footer-item"
                              onClick={() => fetchGraphContext(c)}
                            >
                              <div className="citation-pill">
                                [{c.key}] {c.node_type.toUpperCase()}
                              </div>
                              <span className="citation-item-title">{c.title}</span>
                              <ChevronRight size={12} className="chevron" />
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Pulsing load animation when model retrieves RAG index */}
            {isSending && (
              <div className="message-box-wrapper model typing">
                <div className="message-header-row">
                  <div className="actor-profile">
                    <div className="avatar model pulse-glow"><Cpu size={14} /></div>
                    <span className="actor-name">AXIS RETRIEVING FACT INDEX...</span>
                  </div>
                </div>
                <div className="typing-loader-container">
                  <div className="pulse-dot"></div>
                  <div className="pulse-dot delay-1"></div>
                  <div className="pulse-dot delay-2"></div>
                </div>
              </div>
            )}
            
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input Prompter Container */}
        <footer className="chat-input-bar glass-panel">
          <form onSubmit={handleSendMessage} className="input-form">
            <input 
              type="text" 
              className="prompter-textbox"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={
                !selectedProjectId 
                  ? "Select a Workspace project first to chat..." 
                  : "Query project alignment context (e.g. 'What decisions impact Functional Requirement 1?')..."
              }
              disabled={isSending || !selectedProjectId}
            />
            <button 
              type="submit" 
              className="send-button"
              disabled={isSending || !inputMessage.trim() || !selectedProjectId}
            >
              <Send size={15} />
              <span>Query AI</span>
            </button>
          </form>
        </footer>
      </main>

      {/* 3. Pop-out Graph Inspection Side Panel */}
      {inspectedCitation && (
        <aside className="graph-inspector-drawer glass-panel">
          <div className="drawer-header">
            <div className="drawer-title-block">
              <Database size={15} className="secondary-accent" />
              <h2>GRAPH INSPECTOR</h2>
            </div>
            <button 
              className="close-drawer-btn" 
              onClick={() => setInspectedCitation(null)}
            >
              <X size={16} />
            </button>
          </div>

          <div className="drawer-body">
            
            {/* Cited Node Details */}
            <div className="inspected-metadata-box">
              <div className="meta-row">
                <span className="meta-label">NODE TYPE:</span>
                <span className="meta-val type-badge" style={{ backgroundColor: getNodeTypeColor(inspectedCitation.node_type) + '33', color: getNodeTypeColor(inspectedCitation.node_type) }}>
                  {inspectedCitation.node_type.toUpperCase()}
                </span>
              </div>
              <h3 className="inspected-title">{inspectedCitation.title}</h3>
              <div className="meta-row uuid">
                <span className="meta-label">UUID:</span>
                <span className="meta-val code-font">{inspectedCitation.node_id}</span>
              </div>
              
              {inspectedCitation.snippet && (
                <div className="meta-snippet">
                  <strong>RETRIEVED FACT SNIPPET:</strong>
                  <p>{inspectedCitation.snippet}</p>
                </div>
              )}

              {inspectedCitation.url && (
                <a 
                  href={inspectedCitation.url} 
                  target="_blank" 
                  rel="noreferrer" 
                  className="external-source-link"
                >
                  <Link2 size={13} />
                  <span>Inspect Original GitLab Commit</span>
                </a>
              )}
            </div>

            {/* Interactive Network Graph Viewer */}
            <div className="canvas-container-box">
              <div className="canvas-header">
                <Activity size={12} className="neon-pulse" />
                <span>1-DEGREE BFS NEIGHBORHOOD TRAVERSAL</span>
              </div>
              
              {isGraphLoading ? (
                <div className="canvas-loading-overlay">
                  <RefreshCw size={24} className="spinning" />
                  <span>Traversing Network Edges...</span>
                </div>
              ) : (
                <canvas 
                  ref={canvasRef} 
                  className="network-canvas"
                  onMouseMove={handleCanvasMouseMove}
                  onClick={handleCanvasClick}
                />
              )}

              <div className="canvas-instructions">
                <span>💡 Click an orbiting satellite node to traverse deeper into its relationships</span>
              </div>
            </div>

            {/* Relationship detail list */}
            {inspectedGraphData.edges.length > 0 && (
              <div className="edges-detail-section">
                <h4>ACTIVE RELATIONSHIPS ({inspectedGraphData.edges.length})</h4>
                <div className="edges-scroll-list">
                  {inspectedGraphData.edges.map((e) => {
                    const srcShort = e.source.substring(0, 8);
                    const tgtShort = e.target.substring(0, 8);
                    return (
                      <div key={e.id} className="edge-detail-row">
                        <Terminal size={11} className="dim-accent" />
                        <span className="edge-nodes">{srcShort} ➜ {tgtShort}</span>
                        <span className="edge-type-badge">{e.type}</span>
                        <span className="edge-weight">W: {e.weight.toFixed(1)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          </div>
        </aside>
      )}

      {/* Styled JSX stylesheet to supply premium visual details */}
      <style>{`
        .app-container {
          display: flex;
          width: 100vw;
          height: 100vh;
          background-color: var(--bg-app);
          overflow: hidden;
        }

        /* Sidebar Styling */
        .sidebar-layout {
          width: 320px;
          min-width: 320px;
          display: flex;
          flex-direction: column;
          padding: 1.5rem;
          height: 100%;
        }

        .brand-container {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.75rem;
        }

        .brand-glow-circle {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: var(--primary);
          box-shadow: 0 0 10px var(--primary);
          animation: pulseGlow 2s infinite;
        }

        .brand-title {
          font-size: 1.15rem;
          font-weight: 700;
          letter-spacing: 2px;
          background: linear-gradient(135deg, var(--text-main) 0%, var(--primary) 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .brand-subtitle {
          font-size: 0.65rem;
          font-weight: 600;
          color: var(--text-dim);
          letter-spacing: 3px;
          display: block;
        }

        .health-badge-container {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          background: hsla(220, 20%, 8%, 0.6);
          padding: 6px 12px;
          border-radius: 8px;
          border: 1px solid var(--border-dim);
          margin-bottom: 1.25rem;
        }

        .health-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
        }
        .health-dot.healthy {
          background-color: var(--success);
          box-shadow: 0 0 6px var(--success);
        }
        .health-dot.offline {
          background-color: var(--danger);
          box-shadow: 0 0 6px var(--danger);
        }

        .health-label {
          font-size: 0.65rem;
          font-weight: 600;
          color: var(--text-muted);
          letter-spacing: 0.5px;
        }

        .user-config-panel {
          background: hsla(220, 18%, 12%, 0.4);
          padding: 10px;
          border-radius: 10px;
          border: 1px solid var(--border-dim);
          margin-bottom: 0.75rem;
        }

        .config-label {
          font-size: 0.65rem;
          font-weight: 600;
          color: var(--text-dim);
          letter-spacing: 1px;
          display: flex;
          align-items: center;
          gap: 4px;
          margin-bottom: 6px;
        }

        .config-row {
          display: flex;
          gap: 6px;
        }

        .user-id-input {
          flex: 1;
          background: var(--bg-app);
          border: 1px solid var(--border-dim);
          border-radius: 6px;
          color: var(--text-main);
          font-size: 0.72rem;
          padding: 6px 8px;
          font-family: var(--font-mono);
          outline: none;
          transition: var(--transition-smooth);
        }
        .user-id-input:focus {
          border-color: var(--primary);
        }

        .refresh-config-btn {
          background: var(--primary-glow);
          border: 1px solid hsla(215, 100%, 60%, 0.3);
          border-radius: 6px;
          color: var(--primary);
          padding: 0 8px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: var(--transition-smooth);
        }
        .refresh-config-btn:hover {
          background: var(--primary);
          color: #000;
        }

        .project-selector-container {
          background: hsla(220, 18%, 12%, 0.4);
          padding: 10px;
          border-radius: 10px;
          border: 1px solid var(--border-dim);
          margin-bottom: 1.25rem;
        }

        .project-select-dropdown {
          width: 100%;
          background: var(--bg-app);
          border: 1px solid var(--border-dim);
          border-radius: 6px;
          color: var(--text-main);
          font-size: 0.78rem;
          padding: 6px;
          outline: none;
          cursor: pointer;
          transition: var(--transition-smooth);
        }
        .project-select-dropdown:focus {
          border-color: var(--primary);
        }

        .sidebar-divider {
          height: 1px;
          background: var(--border-dim);
          margin: 0.5rem 0 1rem 0;
        }

        .sessions-header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .sessions-title {
          font-size: 0.75rem;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 1px;
        }

        .new-session-button {
          background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
          border: none;
          color: #000;
          font-weight: 600;
          font-size: 0.72rem;
          padding: 4px 10px;
          border-radius: 6px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          transition: var(--transition-smooth);
        }
        .new-session-button:hover {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px var(--primary-glow);
        }

        .sessions-scroll-list {
          flex: 1;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding-right: 4px;
        }

        .session-item {
          background: hsla(220, 20%, 10%, 0.3);
          border: 1px solid var(--border-dim);
          border-radius: 10px;
          padding: 10px;
          cursor: pointer;
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: var(--transition-smooth);
        }
        .session-item:hover {
          background: hsla(220, 20%, 15%, 0.5);
          border-color: var(--border-glow);
        }
        .session-item.active {
          background: hsla(215, 100%, 60%, 0.08);
          border-color: var(--primary);
        }

        .session-item-left {
          display: flex;
          flex-direction: column;
          gap: 2px;
          overflow: hidden;
          flex: 1;
        }

        .session-item-title {
          font-size: 0.8rem;
          font-weight: 500;
          color: var(--text-main);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .session-item-turns {
          font-size: 0.65rem;
          color: var(--text-dim);
        }

        .session-delete-btn {
          background: transparent;
          border: none;
          color: var(--text-dim);
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          transition: var(--transition-smooth);
        }
        .session-delete-btn:hover {
          color: var(--danger);
          background: hsla(355, 85%, 55%, 0.15);
        }

        .sidebar-footer {
          margin-top: auto;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.65rem;
          color: var(--text-dim);
          padding-top: 1rem;
          border-top: 1px solid var(--border-dim);
        }

        /* Main Area Layout */
        .chat-main-area {
          flex: 1;
          display: flex;
          flex-direction: column;
          height: 100%;
          position: relative;
          background: radial-gradient(circle at top right, hsla(275, 95%, 65%, 0.03), transparent 60%);
        }

        .chat-top-header {
          height: 64px;
          border-radius: 0;
          border-left: none;
          border-right: none;
          border-top: none;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 2rem;
          z-index: 10;
        }

        .active-project-badge {
          display: flex;
          align-items: center;
          gap: 8px;
          background: hsla(215, 100%, 60%, 0.08);
          border: 1px solid hsla(215, 100%, 60%, 0.25);
          padding: 6px 14px;
          border-radius: 99px;
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-main);
          letter-spacing: 0.5px;
        }

        .primary-accent {
          color: var(--primary);
        }
        .secondary-accent {
          color: var(--secondary);
        }
        .success-accent {
          color: var(--success);
        }
        .dim-accent {
          color: var(--text-dim);
        }

        .clear-history-button {
          background: hsla(220, 20%, 15%, 0.4);
          border: 1px solid var(--border-dim);
          color: var(--text-muted);
          border-radius: 8px;
          padding: 6px 12px;
          font-size: 0.72rem;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: var(--transition-smooth);
        }
        .clear-history-button:hover {
          color: var(--text-main);
          border-color: var(--border-glow);
          background: hsla(220, 20%, 20%, 0.6);
        }

        /* Message Thread scroll */
        .chat-scroll-container {
          flex: 1;
          overflow-y: auto;
          padding: 2rem;
        }

        .messages-thread {
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .message-box-wrapper {
          display: flex;
          flex-direction: column;
          animation: fadeIn 0.4s ease-out forwards;
          background: hsla(220, 20%, 12%, 0.2);
          border: 1px solid hsla(220, 20%, 20%, 0.2);
          border-radius: 16px;
          padding: 1.25rem;
          transition: var(--transition-smooth);
        }

        .message-box-wrapper:hover {
          border-color: hsla(220, 20%, 25%, 0.4);
          background: hsla(220, 20%, 12%, 0.35);
        }

        .message-box-wrapper.model {
          border-left: 3px solid var(--primary);
        }

        .message-box-wrapper.user {
          border-left: 3px solid var(--secondary);
          background: hsla(275, 95%, 65%, 0.02);
        }

        .message-header-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .actor-profile {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .avatar {
          width: 24px;
          height: 24px;
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.75rem;
        }
        .avatar.model {
          background: var(--primary-glow);
          color: var(--primary);
          border: 1px solid hsla(215, 100%, 60%, 0.3);
        }
        .avatar.user {
          background: var(--secondary-glow);
          color: var(--secondary);
          border: 1px solid hsla(275, 95%, 65%, 0.3);
        }

        .actor-name {
          font-size: 0.72rem;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 1px;
        }

        .message-time {
          font-size: 0.65rem;
          color: var(--text-dim);
        }

        .message-content-container {
          color: var(--text-main);
          font-size: 0.95rem;
          line-height: 1.6;
        }

        /* Inline formatting components */
        .chat-paragraph {
          margin-bottom: 0.75rem;
        }
        .chat-paragraph:last-child {
          margin-bottom: 0;
        }

        .paragraph-spacer {
          height: 0.75rem;
        }

        .chat-h1 { font-size: 1.4rem; font-weight: 700; margin: 1.25rem 0 0.5rem 0; color: var(--text-main); }
        .chat-h2 { font-size: 1.2rem; font-weight: 600; margin: 1.1rem 0 0.5rem 0; color: var(--text-main); }
        .chat-h3 { font-size: 1.05rem; font-weight: 600; margin: 0.9rem 0 0.4rem 0; color: var(--text-main); }
        .chat-li { margin-left: 1.25rem; margin-bottom: 0.25rem; list-style-type: square; }

        .inline-code {
          font-family: var(--font-mono);
          background: hsla(220, 20%, 15%, 0.7);
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 0.85rem;
          border: 1px solid hsla(220, 20%, 25%, 0.4);
          color: var(--secondary);
        }

        .code-block-container {
          background: hsla(220, 25%, 6%, 0.9);
          border: 1px solid var(--border-dim);
          border-radius: 12px;
          margin: 1rem 0;
          padding: 0;
          overflow: hidden;
        }

        .code-header {
          background: hsla(220, 20%, 10%, 0.8);
          border-bottom: 1px solid var(--border-dim);
          padding: 6px 12px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.65rem;
          color: var(--text-dim);
          font-weight: 700;
        }

        .code-copy-btn {
          background: transparent;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 2px 6px;
          border-radius: 4px;
          transition: var(--transition-smooth);
        }
        .code-copy-btn:hover {
          color: var(--text-main);
          background: hsla(220, 20%, 20%, 0.5);
        }

        .code-block-container code {
          display: block;
          padding: 1rem;
          font-family: var(--font-mono);
          font-size: 0.82rem;
          color: var(--text-main);
          overflow-x: auto;
          line-height: 1.5;
        }

        /* Citation System */
        .cit-badge {
          background: var(--primary-glow);
          border: 1px solid hsla(215, 100%, 60%, 0.35);
          color: var(--primary);
          font-family: var(--font-sans);
          font-weight: 700;
          font-size: 0.72rem;
          padding: 1px 6px;
          border-radius: 6px;
          cursor: pointer;
          margin: 0 3px;
          transition: var(--transition-smooth);
          outline: none;
          display: inline-flex;
          align-items: center;
        }
        .cit-badge:hover {
          background: var(--primary);
          color: #000;
          box-shadow: 0 0 8px var(--primary-glow);
          transform: translateY(-1px);
        }

        .confidence-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          background: hsla(220, 18%, 8%, 0.5);
          border: 1px solid var(--border-dim);
          padding: 8px 14px;
          border-radius: 10px;
          margin-top: 1rem;
        }

        .confidence-left {
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .confidence-text {
          font-size: 0.72rem;
          color: var(--text-muted);
        }

        .confidence-track {
          width: 100px;
          height: 6px;
          background: hsla(220, 20%, 15%, 0.8);
          border-radius: 99px;
          overflow: hidden;
        }

        .confidence-fill {
          height: 100%;
          border-radius: 99px;
          transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .citations-footer {
          margin-top: 1.25rem;
          padding-top: 1rem;
          border-top: 1px dashed var(--border-dim);
        }

        .citations-footer-label {
          display: flex;
          align-items: center;
          gap: 5px;
          font-size: 0.68rem;
          font-weight: 700;
          color: var(--text-dim);
          letter-spacing: 0.75px;
          margin-bottom: 0.5rem;
        }

        .citations-list-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 6px;
        }

        @media (min-width: 600px) {
          .citations-list-grid {
            grid-template-columns: 1fr 1fr;
          }
        }

        .citation-footer-item {
          background: hsla(220, 20%, 8%, 0.4);
          border: 1px solid var(--border-dim);
          border-radius: 8px;
          padding: 6px 10px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          cursor: pointer;
          transition: var(--transition-smooth);
        }
        .citation-footer-item:hover {
          background: hsla(215, 100%, 60%, 0.04);
          border-color: var(--primary);
        }

        .citation-pill {
          font-size: 0.65rem;
          font-weight: 700;
          color: var(--primary);
          background: var(--primary-glow);
          padding: 2px 6px;
          border-radius: 4px;
          border: 1px solid hsla(215, 100%, 60%, 0.2);
          white-space: nowrap;
        }

        .citation-item-title {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin-left: 8px;
          flex: 1;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .chevron {
          color: var(--text-dim);
          transition: var(--transition-smooth);
        }
        .citation-footer-item:hover .chevron {
          color: var(--primary);
          transform: translateX(2px);
        }

        /* Message Typing Loader */
        .typing-loader-container {
          display: flex;
          gap: 6px;
          padding: 8px 14px;
          background: hsla(220, 18%, 8%, 0.4);
          border-radius: 8px;
          width: fit-content;
        }

        .pulse-dot {
          width: 6px;
          height: 6px;
          background-color: var(--primary);
          border-radius: 50%;
          animation: pulseGlow 1.2s infinite ease-in-out;
        }
        .pulse-dot.delay-1 { animation-delay: 0.2s; }
        .pulse-dot.delay-2 { animation-delay: 0.4s; }

        /* Input Container */
        .chat-input-bar {
          height: 72px;
          border-radius: 0;
          border-left: none;
          border-right: none;
          border-bottom: none;
          display: flex;
          align-items: center;
          padding: 0 2rem;
          z-index: 10;
        }

        .input-form {
          width: 100%;
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          gap: 12px;
        }

        .prompter-textbox {
          flex: 1;
          background: var(--bg-input);
          border: 1px solid var(--border-dim);
          border-radius: 10px;
          color: var(--text-main);
          font-size: 0.88rem;
          padding: 0 1rem;
          outline: none;
          transition: var(--transition-smooth);
        }
        .prompter-textbox:focus {
          border-color: var(--primary);
          box-shadow: 0 0 12px -3px var(--primary-glow);
          background: hsla(220, 18%, 16%, 0.7);
        }
        .prompter-textbox:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .send-button {
          background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
          border: none;
          color: #000;
          font-weight: 700;
          font-size: 0.82rem;
          padding: 0 1.25rem;
          border-radius: 10px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: var(--transition-smooth);
        }
        .send-button:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 15px var(--primary-glow);
        }
        .send-button:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        /* Pop-out Graph Inspector Panel */
        .graph-inspector-drawer {
          width: 420px;
          min-width: 420px;
          height: 100%;
          border-radius: 0;
          border-top: none;
          border-bottom: none;
          border-right: none;
          display: flex;
          flex-direction: column;
          z-index: 100;
          box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
          animation: fadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards;
        }

        .drawer-header {
          height: 64px;
          border-bottom: 1px solid var(--border-dim);
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0 1.5rem;
        }

        .drawer-title-block {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .drawer-title-block h2 {
          font-size: 1rem;
          font-weight: 700;
          letter-spacing: 1px;
          color: var(--text-main);
        }

        .close-drawer-btn {
          background: transparent;
          border: none;
          color: var(--text-dim);
          cursor: pointer;
          padding: 4px;
          border-radius: 4px;
          transition: var(--transition-smooth);
        }
        .close-drawer-btn:hover {
          color: var(--text-main);
          background: hsla(220, 20%, 20%, 0.5);
        }

        .drawer-body {
          flex: 1;
          overflow-y: auto;
          padding: 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .inspected-metadata-box {
          background: hsla(220, 20%, 8%, 0.4);
          border: 1px solid var(--border-dim);
          border-radius: 12px;
          padding: 1.25rem;
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .meta-row {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .meta-row.uuid {
          margin-top: 4px;
          font-size: 0.7rem;
        }

        .meta-label {
          font-size: 0.65rem;
          font-weight: 700;
          color: var(--text-dim);
          letter-spacing: 0.5px;
        }

        .meta-val {
          font-size: 0.72rem;
          font-weight: 600;
        }
        .meta-val.code-font {
          font-family: var(--font-mono);
          color: var(--text-muted);
        }

        .type-badge {
          font-size: 0.62rem;
          font-weight: 800;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .inspected-title {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-main);
          line-height: 1.4;
        }

        .meta-snippet {
          background: hsla(220, 20%, 6%, 0.5);
          border: 1px solid var(--border-dim);
          border-radius: 8px;
          padding: 10px;
          margin-top: 4px;
        }
        .meta-snippet strong {
          font-size: 0.65rem;
          color: var(--primary);
          display: block;
          margin-bottom: 4px;
          letter-spacing: 0.5px;
        }
        .meta-snippet p {
          font-size: 0.78rem;
          color: var(--text-muted);
          line-height: 1.5;
        }

        .external-source-link {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          background: var(--primary-glow);
          border: 1px solid hsla(215, 100%, 60%, 0.3);
          border-radius: 8px;
          color: var(--primary);
          font-size: 0.75rem;
          font-weight: 600;
          padding: 8px;
          text-align: center;
          transition: var(--transition-smooth);
          margin-top: 4px;
        }
        .external-source-link:hover {
          background: var(--primary);
          color: #000;
          box-shadow: 0 0 10px var(--primary-glow);
        }

        /* Canvas Panel */
        .canvas-container-box {
          background: hsla(220, 20%, 8%, 0.25);
          border: 1px solid var(--border-dim);
          border-radius: 16px;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          position: relative;
        }

        .canvas-header {
          background: hsla(220, 20%, 8%, 0.6);
          border-bottom: 1px solid var(--border-dim);
          padding: 8px 12px;
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.65rem;
          font-weight: 700;
          color: var(--text-muted);
          letter-spacing: 0.75px;
        }

        .network-canvas {
          width: 100%;
          height: 280px;
          background: radial-gradient(circle at center, hsla(220, 25%, 8%, 0.7) 0%, hsla(222, 24%, 4%, 0.95) 100%);
        }

        .canvas-loading-overlay {
          width: 100%;
          height: 280px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
          background: hsla(220, 20%, 5%, 0.85);
          color: var(--text-muted);
          font-size: 0.8rem;
        }

        .spinning {
          animation: spin 2s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .canvas-instructions {
          padding: 8px;
          font-size: 0.62rem;
          color: var(--text-dim);
          text-align: center;
          border-top: 1px solid var(--border-dim);
          background: hsla(220, 20%, 6%, 0.4);
        }

        /* Relationship list */
        .edges-detail-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .edges-detail-section h4 {
          font-size: 0.72rem;
          font-weight: 750;
          color: var(--text-muted);
          letter-spacing: 0.75px;
        }

        .edges-scroll-list {
          display: flex;
          flex-direction: column;
          gap: 6px;
          max-height: 140px;
          overflow-y: auto;
          padding-right: 4px;
        }

        .edge-detail-row {
          background: hsla(220, 20%, 8%, 0.3);
          border: 1px solid var(--border-dim);
          border-radius: 6px;
          padding: 6px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.7rem;
        }

        .edge-nodes {
          font-family: var(--font-mono);
          color: var(--text-muted);
        }

        .edge-type-badge {
          background: hsla(275, 95%, 65%, 0.15);
          color: var(--secondary);
          border: 1px solid hsla(275, 95%, 65%, 0.3);
          font-size: 0.58rem;
          font-weight: 800;
          padding: 1px 4px;
          border-radius: 4px;
        }

        .edge-weight {
          margin-left: auto;
          color: var(--text-dim);
          font-weight: 600;
        }
      `}</style>
    </div>
  );
}

export default App;
