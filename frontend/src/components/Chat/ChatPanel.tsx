import { useRef, useEffect, useState } from 'react';
import { Send, User, Bot, Sparkles, Plus, Network, RotateCcw, ChevronDown, ChevronUp, Zap, ArrowUpNarrowWide, Layers } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Message, Citation, RagasEval, AdvancedRetrievalInfo } from '../../types';

interface ChatPanelProps {
  messages: Message[];
  inputValue: string;
  setInputValue: (val: string) => void;
  handleSendMessage: (e?: React.FormEvent) => void;
  isLoading: boolean;
  onCitationClick: (citation: Citation) => void;
  onNewChat?: () => void;
}

const SUGGESTED_PROMPTS = [
  { icon: '🔍', text: 'What is the current scope of our active feature?' },
  { icon: '⚡', text: 'Show me requirement conflicts in this project' },
  { icon: '📋', text: 'What changed since last sprint?' },
  { icon: '🔗', text: 'Which components depend on the auth module?' },
];

// ─── RAGAS Score Badge ────────────────────────────────────────────────────────

function getRagasColor(score: number): string {
  if (score >= 0.8) return '#10b981';
  if (score >= 0.5) return '#f59e0b';
  return '#ef4444';
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = getRagasColor(value);
  return (
    <div style={{ marginBottom: '6px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>{label}</span>
        <span style={{ fontSize: '0.65rem', color, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{(value * 100).toFixed(0)}%</span>
      </div>
      <div style={{ height: '4px', borderRadius: '2px', background: 'var(--bg-elevated)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${value * 100}%`, background: `linear-gradient(90deg, ${color}, ${color}88)`, borderRadius: '2px', transition: 'width 0.5s ease' }} />
      </div>
    </div>
  );
}

function RagasEvalBadge({ ragas }: { ragas: RagasEval }) {
  const [open, setOpen] = useState(false);

  // Show a pulsing "Evaluating..." badge while RAGAS runs in the background
  if (!ragas.evaluated) {
    return (
      <div style={{
        marginTop: '10px',
        border: '1px solid #6366f133',
        borderRadius: '10px',
        overflow: 'hidden',
        background: '#6366f108',
        padding: '6px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
      }}>
        <style>{`
          @keyframes ragas-pulse {
            0%, 100% { opacity: 1; } 50% { opacity: 0.4; }
          }
        `}</style>
        <Zap size={11} style={{ color: '#6366f1', animation: 'ragas-pulse 1.5s ease-in-out infinite' }} />
        <span style={{ fontSize: '0.65rem', fontWeight: 600, color: '#6366f1', fontFamily: 'var(--font-mono)', animation: 'ragas-pulse 1.5s ease-in-out infinite' }}>
          RAGAS Evaluating…
        </span>
        <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', marginLeft: '2px' }}>
          LLM judge running in background
        </span>
      </div>
    );
  }

  const score = ragas.ragas_score;
  const color = getRagasColor(score);

  return (
    <div style={{
      marginTop: '10px',
      border: `1px solid ${color}33`,
      borderRadius: '10px',
      overflow: 'hidden',
      background: `${color}08`,
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '6px 10px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text-secondary)',
        }}
      >
        <Zap size={11} style={{ color }} />
        <span style={{ fontSize: '0.65rem', fontWeight: 600, color, fontFamily: 'var(--font-mono)' }}>
          RAGAS {(score * 100).toFixed(0)}%
        </span>
        <span style={{ fontSize: '0.6rem', color: 'var(--text-tertiary)', marginLeft: '2px' }}>
          Eval Report
        </span>
        <span style={{ marginLeft: 'auto' }}>
          {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </span>
      </button>

      {open && (
        <div style={{ padding: '8px 12px 10px', borderTop: `1px solid ${color}22` }}>
          <ScoreBar label="Faithfulness" value={ragas.faithfulness} />
          <ScoreBar label="Answer Relevancy" value={ragas.answer_relevancy} />
          <ScoreBar label="Context Precision" value={ragas.context_precision} />
          <ScoreBar label="Entity Recall" value={ragas.context_entity_recall} />
          <div style={{ marginTop: '8px', fontSize: '0.6rem', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
            Evaluated by Gemini as LLM judge · RAGAS v0.2
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Advanced Retrieval Pills ─────────────────────────────────────────────────

function AdvancedRetrievalPills({ info }: { info: AdvancedRetrievalInfo }) {
  // Always show the strategy pills — these are determined before RAGAS runs
  const pills: { icon: React.ReactNode; label: string; color: string }[] = [
    { icon: <ArrowUpNarrowWide size={9} />, label: 'Step-Back Query', color: '#8b5cf6' },
    { icon: <Layers size={9} />, label: info.parent_documents_expanded > 0 ? `+${info.parent_documents_expanded} Parent Docs` : 'Parent-Doc Retrieval', color: '#3b82f6' },
    { icon: <Zap size={9} />, label: info.contextual_compression_applied > 0 ? `${info.contextual_compression_applied} Compressed` : 'Ctx Compression', color: '#06b6d4' },
  ];

  // Dim pills for strategies that didn't activate this turn
  const activePills = pills.map((pill, i) => ({
    ...pill,
    active: i === 0 ? info.step_back_used : i === 1 ? info.parent_documents_expanded > 0 : info.contextual_compression_applied > 0,
  }));

  return (
    <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '8px' }}>
      {activePills.map((pill, i) => (
        <span key={i} title={pill.active ? 'Active this turn' : 'Not triggered this turn'} style={{
          display: 'inline-flex', alignItems: 'center', gap: '3px',
          padding: '2px 7px', borderRadius: '20px',
          fontSize: '0.58rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
          background: pill.active ? `${pill.color}18` : 'var(--bg-elevated)',
          color: pill.active ? pill.color : 'var(--text-tertiary)',
          border: `1px solid ${pill.active ? pill.color + '44' : 'var(--border-subtle)'}`,
          opacity: pill.active ? 1 : 0.5,
          transition: 'all 0.2s',
        }}>
          {pill.icon}
          {pill.label}
        </span>
      ))}
    </div>
  );
}

// ─── Main ChatPanel ───────────────────────────────────────────────────────────

export default function ChatPanel({
  messages,
  inputValue,
  setInputValue,
  handleSendMessage,
  isLoading,
  onCitationClick,
  onNewChat,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [localInput, setLocalInput] = useState(inputValue);

  useEffect(() => {
    setLocalInput(inputValue);
  }, [inputValue]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setLocalInput(val);
    setInputValue(val);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (localInput.trim() && !isLoading) {
        handleSendMessage();
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
        }
      }
    }
  };

  const handlePromptClick = (prompt: string) => {
    setLocalInput(prompt);
    setInputValue(prompt);
    textareaRef.current?.focus();
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    handleSendMessage(e);
  };

  const renderMessageContent = (content: string) => (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  );

  const getConfidenceColor = (score: number) => {
    if (score > 0.8) return 'var(--emerald)';
    if (score > 0.5) return 'var(--amber)';
    return 'var(--red)';
  };

  const showMessages = messages.filter(m => m.id !== 'welcome' || messages.length === 1);
  const isEmptyChat = messages.length === 1 && messages[0]?.id === 'welcome';

  return (
    <div className="chat-container">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-title">
          <div className="chat-title-icon">
            <Sparkles size={14} />
          </div>
          <div>
            <h2>Project Assistant</h2>
          </div>
        </div>
        <div className="chat-actions">
          <button className="icon-btn" title="View Knowledge Graph">
            <Network size={14} />
          </button>
          {onNewChat && (
            <button className="icon-btn" onClick={onNewChat} title="New conversation">
              <Plus size={14} />
            </button>
          )}
          <button className="icon-btn" title="Clear conversation" onClick={onNewChat}>
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {isEmptyChat ? (
          <div className="empty-chat">
            <div className="empty-chat-orb">
              <Sparkles size={28} />
            </div>
            <h3>Ask Axis anything</h3>
            <p>Query your project's requirements, decisions, dependencies, and change history using natural language.</p>

            <div className="empty-prompts">
              {SUGGESTED_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  className="prompt-chip"
                  onClick={() => handlePromptClick(prompt.text)}
                >
                  <span>{prompt.icon}</span>
                  {prompt.text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          showMessages.map((message) => (
            <div key={message.id} className={`message-wrapper ${message.role}`}>
              <div className="message-avatar">
                {message.role === 'user' ? <User size={14} /> : <Bot size={14} />}
              </div>

              <div className="message-content-wrapper">
                <div className="message-meta">
                   {message.role === 'user' ? 'You' : 'Axis AI'} · {message.timestamp}
                </div>

                <div className={`message ${message.role}`}>
                  {renderMessageContent(message.content)}

                  {/* Citations */}
                  {message.role === 'model' && message.citations && message.citations.length > 0 && (
                    <div className="citations-container">
                      <div className="citations-header">Sources</div>
                      <div className="citations-list">
                        {message.citations.map((citation) => (
                          <div
                            key={citation.key}
                            className="citation-tag"
                            onClick={() => onCitationClick(citation)}
                            title={`Explore: ${citation.title}`}
                          >
                            <span className="citation-number">[{citation.key}]</span>
                            <span className="citation-title">{citation.title}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Confidence bar */}
                  {message.role === 'model' && message.confidence_score !== undefined && message.confidence_score > 0 && (
                    <div className="confidence-indicator">
                      <div className="confidence-bar">
                        <div
                          className="confidence-fill"
                          style={{
                            width: `${message.confidence_score * 100}%`,
                            background: `linear-gradient(90deg, ${getConfidenceColor(message.confidence_score)}, ${getConfidenceColor(message.confidence_score)}88)`,
                          }}
                        />
                      </div>
                      <span className="confidence-text">{Math.round(message.confidence_score * 100)}%</span>
                    </div>
                  )}

                  {/* Advanced Retrieval pills — always shown for AI messages */}
                  {message.role === 'model' && message.advanced_retrieval && (
                    <AdvancedRetrievalPills info={message.advanced_retrieval} />
                  )}

                  {/* RAGAS Eval Badge — shows pending state while evaluating, results when done */}
                  {message.role === 'model' && message.ragas_eval && (
                    <RagasEvalBadge ragas={message.ragas_eval} />
                  )}
                </div>
              </div>
            </div>
          ))
        )}

        {/* Typing indicator */}
        {isLoading && (
          <div className="message-wrapper model loading">
            <div className="message-avatar">
              <Bot size={14} />
            </div>
            <div className="message-content-wrapper">
              <div className="message-meta">Axis AI · thinking...</div>
              <div className="message model">
                <div className="typing-indicator">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-container">
        <form onSubmit={handleFormSubmit} className="chat-form">
          <textarea
            ref={textareaRef}
            value={localInput}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your project requirements, decisions, or code…"
            disabled={isLoading}
            rows={1}
          />
          <button type="submit" className="chat-send-btn" disabled={!localInput.trim() || isLoading}>
            <Send size={15} />
          </button>
        </form>
        <div className="chat-input-hint">
          Press <kbd style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: 4, padding: '0 4px', fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>Enter</kbd> to send · <kbd style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: 4, padding: '0 4px', fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>Shift+Enter</kbd> for newline
        </div>
      </div>
    </div>
  );
}
