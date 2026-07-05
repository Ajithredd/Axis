import { useEffect, useRef, useState } from 'react';
import { ZoomIn, ZoomOut, Maximize2, ScanSearch } from 'lucide-react';
import { GraphNode, GraphEdge } from '../../types';

interface FeatureGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  highlightedNodes: Set<string>;
  onNodeClick: (node: GraphNode) => void;
  isLoading: boolean;
}

// Theme-matched node colors for dark mode
const NODE_COLORS: Record<string, string> = {
  feature:     'hsl(325, 90%, 62%)',
  requirement: 'hsl(158, 80%, 48%)',
  decision:    'hsl(262, 90%, 65%)',
  stakeholder: 'hsl(38, 95%, 60%)',
  event:       'hsl(185, 100%, 56%)',
  default:     'hsl(220, 30%, 65%)',
};

export default function FeatureGraph({ nodes = [], edges = [], highlightedNodes = new Set(), onNodeClick, isLoading }: FeatureGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const animFrameRef = useRef<number>(0);
  const zoomRef = useRef(zoom);
  const panRef = useRef(pan);

  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panRef.current = pan; }, [pan]);

  // ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(entries => {
      for (const entry of entries) {
        setDimensions({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dimensions.width === 0 || dimensions.height === 0 || nodes.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = dimensions.width * dpr;
    canvas.height = dimensions.height * dpr;
    ctx.scale(dpr, dpr);

    let animId: number;

    const render = () => {
      animFrameRef.current += 1;
      const frame = animFrameRef.current;

      ctx.clearRect(0, 0, dimensions.width, dimensions.height);

      // Dark canvas background
      ctx.fillStyle = 'transparent';
      ctx.fillRect(0, 0, dimensions.width, dimensions.height);

      ctx.save();
      ctx.translate(dimensions.width / 2 + pan.x, dimensions.height / 2 + pan.y);
      ctx.scale(zoom, zoom);

      // Calculate positions
      const positions = new Map<string, { x: number; y: number }>();
      nodes.forEach(node => {
        if (node.isCenter) {
          positions.set(node.id, { x: 0, y: 0 });
        } else if (node.orbitRadius !== undefined && node.orbitSpeed !== undefined && node.angle !== undefined) {
          const angle = node.angle + frame * node.orbitSpeed;
          positions.set(node.id, {
            x: Math.cos(angle) * node.orbitRadius,
            y: Math.sin(angle) * node.orbitRadius,
          });
        } else {
          positions.set(node.id, { x: node.x, y: node.y });
        }
      });

      nodePositionsRef.current = positions;

      // Draw orbit rings for center node
      const centerNode = nodes.find(n => n.isCenter);
      if (centerNode) {
        const orbitRadii = new Set(nodes.filter(n => !n.isCenter && n.orbitRadius).map(n => n.orbitRadius!));
        orbitRadii.forEach(r => {
          ctx.beginPath();
          ctx.arc(0, 0, r, 0, Math.PI * 2);
          ctx.strokeStyle = 'hsla(262, 90%, 65%, 0.08)';
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 8]);
          ctx.stroke();
          ctx.setLineDash([]);
        });
      }

      // Draw edges
      edges.forEach(edge => {
        const src = positions.get(edge.source);
        const tgt = positions.get(edge.target);
        if (!src || !tgt) return;

        const isHighlighted = highlightedNodes.size > 0 && (highlightedNodes.has(edge.source) || highlightedNodes.has(edge.target));
        const isHovered = hoveredNode === edge.source || hoveredNode === edge.target;

        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);

        if (isHovered || isHighlighted) {
          ctx.strokeStyle = 'hsla(262, 90%, 65%, 0.5)';
          ctx.lineWidth = edge.weight * 1.5;
        } else {
          ctx.strokeStyle = 'hsla(220, 30%, 100%, 0.08)';
          ctx.lineWidth = edge.weight * 0.6;
        }

        ctx.stroke();
      });

      // Draw nodes
      nodes.forEach(node => {
        const pos = positions.get(node.id);
        if (!pos) return;

        const isHovered = hoveredNode === node.id;
        const isHighlighted = highlightedNodes.has(node.id);
        const isDimmed = highlightedNodes.size > 0 && !isHighlighted && !isHovered;
        const getCleanTypeKey = (type: string | null | undefined): string => {
          if (!type) return 'default';
          const t = type.toLowerCase().trim();
          if (t.startsWith('feature')) return 'feature';
          if (t.startsWith('requirement')) return 'requirement';
          if (t.startsWith('decision')) return 'decision';
          if (t.startsWith('stakeholder')) return 'stakeholder';
          if (t.startsWith('event')) return 'event';
          return 'default';
        };

        const color = node.isCenter ? 'hsl(185, 100%, 56%)' : (NODE_COLORS[getCleanTypeKey(node.type)] || NODE_COLORS.default);
        const radius = node.radius + (isHovered ? 4 : 0);

        ctx.globalAlpha = isDimmed ? 0.2 : 1;

        // Glow effect
        if (isHovered || isHighlighted || node.isCenter) {
          ctx.shadowColor = color;
          ctx.shadowBlur = node.isCenter ? 24 : 14;
        } else {
          ctx.shadowColor = 'transparent';
          ctx.shadowBlur = 0;
        }

        // Node body with gradient
        const gradient = ctx.createRadialGradient(pos.x - radius * 0.3, pos.y - radius * 0.3, 0, pos.x, pos.y, radius);
        gradient.addColorStop(0, color + 'FF');
        gradient.addColorStop(1, color + 'AA');

        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        // Border ring
        ctx.strokeStyle = node.isCenter ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.15)';
        ctx.lineWidth = node.isCenter ? 2 : 1;
        ctx.stroke();

        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1;

        // Label
        if (node.isCenter || isHovered) {
          ctx.globalAlpha = isDimmed && !isHovered ? 0.4 : 1;
          const nodeTitle = node.title || '';
          const label = nodeTitle.length > 20 ? nodeTitle.substring(0, 18) + '…' : nodeTitle;
          const fontSize = node.isCenter ? 13 : 11;
          ctx.font = `${node.isCenter ? '700' : '500'} ${fontSize}px 'Inter', sans-serif`;

          const textWidth = ctx.measureText(label).width;
          const padX = 7, padY = 4;
          const textX = pos.x;
          const textY = pos.y + radius + 10;

          // Text background pill
          ctx.fillStyle = 'rgba(13, 15, 25, 0.85)';
          ctx.beginPath();
          if (ctx.roundRect) {
            ctx.roundRect(textX - textWidth / 2 - padX, textY - fontSize / 2 - padY, textWidth + padX * 2, fontSize + padY * 2, 6);
          } else {
            ctx.rect(textX - textWidth / 2 - padX, textY - fontSize / 2 - padY, textWidth + padX * 2, fontSize + padY * 2);
          }
          ctx.fill();

          // Text
          ctx.fillStyle = node.isCenter ? '#E0F7FA' : '#CBD5E1';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(label, textX, textY);

          ctx.globalAlpha = 1;
        }

        // Center node inner icon indicator
        if (node.isCenter) {
          ctx.fillStyle = 'rgba(255,255,255,0.7)';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.font = '700 11px Inter, sans-serif';
          ctx.fillText('●', pos.x, pos.y);
        }
      });

      ctx.restore();
      animId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animId);
  }, [dimensions, nodes, edges, zoom, pan, hoveredNode, highlightedNodes]);

  // Wheel zoom
  useEffect(() => {
    const wrapper = containerRef.current?.querySelector('.canvas-wrapper') as HTMLElement | null;
    if (!wrapper) return;
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      setZoom(prev => Math.max(0.2, Math.min(5, prev - e.deltaY * 0.001)));
    };
    wrapper.addEventListener('wheel', handleWheel, { passive: false });
    return () => wrapper.removeEventListener('wheel', handleWheel);
  }, []);

  const getMouseGraphPos = (e: React.MouseEvent) => {
    if (!containerRef.current || dimensions.width === 0) return null;
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - dimensions.width / 2 - pan.x) / zoom,
      y: (e.clientY - rect.top - dimensions.height / 2 - pan.y) / zoom,
    };
  };

  const findHoveredNode = (mousePos: { x: number; y: number }) => {
    for (const [nodeId, pos] of nodePositionsRef.current.entries()) {
      const node = nodes.find(n => n.id === nodeId);
      if (!node) continue;
      const dist = Math.sqrt((mousePos.x - pos.x) ** 2 + (mousePos.y - pos.y) ** 2);
      if (dist <= node.radius + 5) return nodeId;
    }
    return null;
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
      return;
    }
    const pos = getMouseGraphPos(e);
    if (pos && nodes.length > 0) {
      const found = findHoveredNode(pos);
      if (found !== hoveredNode) setHoveredNode(found);
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleCanvasClick = () => {
    if (hoveredNode) {
      const node = nodes.find(n => n.id === hoveredNode);
      if (node) onNodeClick(node);
    }
  };

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  return (
    <div className="graph-container" ref={containerRef}>
      <div className="graph-header">
        <h3>Feature Intelligence Graph</h3>
        <div className="graph-controls">
          <button onClick={() => setZoom(z => Math.min(5, z + 0.25))} title="Zoom In"><ZoomIn size={13} /></button>
          <button onClick={() => setZoom(z => Math.max(0.2, z - 0.25))} title="Zoom Out"><ZoomOut size={13} /></button>
          <span className="ctrl-divider" />
          <button onClick={resetView} title="Fit to View"><Maximize2 size={13} /></button>
          <button title="Filter"><ScanSearch size={13} /></button>
        </div>
      </div>

      <div
        className="canvas-wrapper"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleCanvasClick}
        style={{ cursor: isDragging ? 'grabbing' : hoveredNode ? 'pointer' : 'grab' }}
      >
        {isLoading && nodes.length === 0 ? (
          <div className="graph-loading">
            <div className="graph-pulse" />
            <p>Analyzing Project Ecosystem…</p>
          </div>
        ) : (
          <canvas ref={canvasRef} className="feature-canvas" />
        )}
      </div>

      <div className="graph-legend">
        <div className="legend-item"><span className="dot center" />Current Node</div>
        <div className="legend-item"><span className="dot feature" />Feature</div>
        <div className="legend-item"><span className="dot requirement" />Requirement</div>
        <div className="legend-item"><span className="dot decision" />Decision</div>
        <div className="legend-item"><span className="dot stakeholder" />Stakeholder</div>
      </div>
    </div>
  );
}
