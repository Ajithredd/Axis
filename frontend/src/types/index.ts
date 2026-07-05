export interface Project {
  id: string;
  name: string;
  description: string;
  connectors: Array<{ type: string; status: string }>;
}

export interface Citation {
  key: number;
  node_id: string;
  node_type: string;
  title: string;
  url?: string | null;
  snippet?: string | null;
}

export interface RagasEval {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
  context_entity_recall: number;
  ragas_score: number;
  evaluated: boolean;
  error?: string | null;
}

export interface AdvancedRetrievalInfo {
  step_back_used: boolean;
  parent_documents_expanded: number;
  contextual_compression_applied: number;
}

export interface Message {
  id: string;
  role: 'user' | 'model';
  content: string;
  confidence_score?: number;
  citations?: Citation[];
  timestamp: string;
  ragas_eval?: RagasEval;
  advanced_retrieval?: AdvancedRetrievalInfo;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
}

export interface GraphNode {
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

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  weight: number;
}
