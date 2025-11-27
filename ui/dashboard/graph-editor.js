// Graph Editor JavaScript
(function() {
  const API_HOST = "localhost:8000";
  const API_BASE = `http://${API_HOST}/api`;
  
  let graphState = {
    nodes: [],
    connections: [],
    selectedNode: null,
    dragging: { node: null, offsetX: 0, offsetY: 0, active: false },
    connecting: { from: null, fromPort: null }
  };
  
  let canvas = null;
  let svg = null;
  let zoom = 1.0;
  let panX = 0;
  let panY = 0;
  
  // Initialize graph editor
  function initGraphEditor() {
    console.log('Initializing graph editor...');
    canvas = document.getElementById('graph-canvas');
    if (!canvas) {
      console.error('Graph canvas not found!');
      return;
    }
    
    console.log('Canvas found:', canvas);
    svg = canvas;
    
    // Set initial canvas size (even if tab is hidden)
    canvas.setAttribute('width', '1200');
    canvas.setAttribute('height', '800');
    
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        console.log('Switching to tab:', tab);
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => {
          c.classList.remove('active');
          c.style.display = 'none';
        });
        btn.classList.add('active');
        const tabContent = document.getElementById(`${tab}-tab`);
        if (tabContent) {
          tabContent.classList.add('active');
          tabContent.style.display = tab === 'graph' ? 'block' : 'grid';
          console.log('Tab content displayed:', tabContent.style.display);
        }
        
        if (tab === 'graph') {
          // Reload graph when switching to graph tab
          setTimeout(() => {
            console.log('Updating canvas size and loading graph...');
            updateCanvasSize();
            loadGraphState();
          }, 200);
        }
      });
    });
    
    // Load initial graph state
    loadGraphState();
    setupEventListeners();
    console.log('Graph editor initialized!');
  }
  
  function updateCanvasSize() {
    if (!canvas) return;
    const wrapper = canvas.parentElement;
    if (wrapper) {
      const rect = wrapper.getBoundingClientRect();
      const width = Math.max(800, rect.width || 1200);
      const height = Math.max(600, rect.height || 800);
      canvas.setAttribute('width', width);
      canvas.setAttribute('height', height);
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      renderGraph();
    } else {
      // Fallback if wrapper not found
      canvas.setAttribute('width', 1200);
      canvas.setAttribute('height', 800);
      renderGraph();
    }
  }
  
  // Load current graph from server
  async function loadGraphState() {
    try {
      console.log('Loading graph state from:', `${API_BASE}/graph/current`);
      const response = await fetch(`${API_BASE}/graph/current`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data = await response.json();
      console.log('Graph state loaded:', data);
      graphState.nodes = data.nodes || [];
      graphState.connections = data.connections || [];
      console.log(`Loaded ${graphState.nodes.length} nodes, ${graphState.connections.length} connections`);
      renderGraph();
    } catch (error) {
      console.error('Failed to load graph:', error);
      alert(`Failed to load graph: ${error.message}`);
    }
  }
  
  // Render graph to SVG
  function renderGraph() {
    if (!svg) {
      console.warn('SVG not available for rendering');
      return;
    }
    
    console.log('Rendering graph:', graphState.nodes.length, 'nodes');
    
    // Clear existing
    const existing = svg.querySelectorAll('.connection-line, .graph-node');
    console.log('Clearing', existing.length, 'existing elements');
    existing.forEach(el => el.remove());
    
    // Render connections first (so they appear behind nodes)
    graphState.connections.forEach(conn => {
      const fromNode = graphState.nodes.find(n => n.id === conn.from);
      const toNode = graphState.nodes.find(n => n.id === conn.to);
      if (fromNode && toNode) {
        drawConnection(fromNode, toNode);
      }
    });
    
    // Render nodes
    graphState.nodes.forEach(node => {
      drawNode(node);
    });
    
    console.log('Graph rendered!');
  }
  
  // Draw a node
  function drawNode(node) {
    const pos = node.position || { x: Math.random() * 400 + 100, y: Math.random() * 300 + 100 };
    const x = typeof pos === 'object' ? (pos.x || 100) : 100;
    const y = typeof pos === 'object' ? (pos.y || 100) : 100;
    
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'graph-node');
    g.setAttribute('data-node-id', node.id);
    g.setAttribute('transform', `translate(${x}, ${y})`);
    
    // Node rectangle
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', '140');
    rect.setAttribute('height', '70');
    rect.setAttribute('rx', '8');
    rect.setAttribute('class', 'node-box');
    g.appendChild(rect);
    
    // Node label
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', '70');
    text.setAttribute('y', '40');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('class', 'node-label');
    text.textContent = node.name;
    g.appendChild(text);
    
    // Kind label
    const kindText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    kindText.setAttribute('x', '70');
    kindText.setAttribute('y', '58');
    kindText.setAttribute('text-anchor', 'middle');
    kindText.setAttribute('class', 'node-kind');
    kindText.textContent = node.kind;
    g.appendChild(kindText);
    
    // Input port (left side)
    const inputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    inputPort.setAttribute('cx', '0');
    inputPort.setAttribute('cy', '35');
    inputPort.setAttribute('r', '6');
    inputPort.setAttribute('class', 'port port-input');
    inputPort.setAttribute('data-port-type', 'input');
    g.appendChild(inputPort);
    
    // Output port (right side)
    const outputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    outputPort.setAttribute('cx', '140');
    outputPort.setAttribute('cy', '35');
    outputPort.setAttribute('r', '6');
    outputPort.setAttribute('class', 'port port-output');
    outputPort.setAttribute('data-port-type', 'output');
    g.appendChild(outputPort);
    
    svg.appendChild(g);
  }
  
  // Draw connection line
  function drawConnection(fromNode, toNode) {
    const fromPos = fromNode.position || { x: 100, y: 100 };
    const toPos = toNode.position || { x: 200, y: 200 };
    
    const x1 = (typeof fromPos === 'object' ? fromPos.x : 100) + 140;
    const y1 = (typeof fromPos === 'object' ? fromPos.y : 100) + 35;
    const x2 = typeof toPos === 'object' ? toPos.x : 200;
    const y2 = (typeof toPos === 'object' ? toPos.y : 200) + 35;
    
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const d = `M ${x1} ${y1} L ${x2} ${y2}`;
    path.setAttribute('d', d);
    path.setAttribute('class', 'connection-line');
    path.setAttribute('data-from', fromNode.id);
    path.setAttribute('data-to', toNode.id);
    svg.appendChild(path);
  }
  
  // Setup event listeners
  function setupEventListeners() {
    if (!canvas) return;
    
    // Palette drag
    document.querySelectorAll('.palette-item').forEach(item => {
      item.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('kind', item.dataset.kind);
        e.dataTransfer.effectAllowed = 'copy';
      });
    });
    
    // Canvas drop
    canvas.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
    });
    
    canvas.addEventListener('drop', handleCanvasDrop);
    
    // Node interaction
    canvas.addEventListener('mousedown', handleCanvasMouseDown);
    canvas.addEventListener('mousemove', handleCanvasMouseMove);
    canvas.addEventListener('mouseup', handleCanvasMouseUp);
    canvas.addEventListener('dblclick', handleCanvasDoubleClick);
    
    // Save layout button
    const saveBtn = document.getElementById('save-layout-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', saveLayout);
    }
  }
  
  // Handle dropping node from palette
  async function handleCanvasDrop(e) {
    e.preventDefault();
    const kind = e.dataTransfer.getData('kind');
    if (!kind) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left - panX) / zoom;
    const y = (e.clientY - rect.top - panY) / zoom;
    
    const nodeId = `node_${Date.now()}`;
    
    try {
      const response = await fetch(`${API_BASE}/graph/nodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: nodeId,
          kind: kind,
          x: x,
          y: y,
          params: {}
        })
      });
      
      if (response.ok) {
        await loadGraphState();
      } else {
        const error = await response.json();
        alert(`Failed to add node: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to add node:', error);
      alert('Failed to add node. Check console for details.');
    }
  }
  
  // Handle canvas mouse events
  function handleCanvasMouseDown(e) {
    const target = e.target;
    const nodeElement = target.closest('.graph-node');
    const port = target.closest('.port');
    
    if (port && nodeElement) {
      // Port clicked - start connection
      const nodeId = nodeElement.dataset.nodeId;
      const portType = port.dataset.portType;
      
      if (portType === 'output') {
        graphState.connecting.from = nodeId;
        graphState.connecting.fromPort = port;
        canvas.style.cursor = 'crosshair';
      } else if (portType === 'input' && graphState.connecting.from) {
        // Complete connection
        createConnection(graphState.connecting.from, nodeId);
        graphState.connecting.from = null;
        graphState.connecting.fromPort = null;
        canvas.style.cursor = 'default';
      }
      return;
    }
    
    if (nodeElement) {
      // Node clicked - start drag
      const nodeId = nodeElement.dataset.nodeId;
      const node = graphState.nodes.find(n => n.id === nodeId);
      if (node) {
        const pos = node.position || { x: 0, y: 0 };
        const posX = typeof pos === 'object' ? pos.x : 0;
        const posY = typeof pos === 'object' ? pos.y : 0;
        const rect = canvas.getBoundingClientRect();
        graphState.dragging = {
          node: node,
          offsetX: (e.clientX - rect.left - panX) / zoom - posX,
          offsetY: (e.clientY - rect.top - panY) / zoom - posY,
          active: true
        };
        canvas.style.cursor = 'grabbing';
      }
    } else if (target.classList.contains('connection-line')) {
      // Connection clicked - delete it
      const from = target.dataset.from;
      const to = target.dataset.to;
      if (confirm('Delete this connection?')) {
        deleteConnection(from, to);
      }
    }
  }
  
  function handleCanvasMouseMove(e) {
    if (graphState.dragging.active && graphState.dragging.node) {
      const rect = canvas.getBoundingClientRect();
      const x = (e.clientX - rect.left - panX) / zoom - graphState.dragging.offsetX;
      const y = (e.clientY - rect.top - panY) / zoom - graphState.dragging.offsetY;
      
      // Ensure position is an object
      if (!graphState.dragging.node.position || typeof graphState.dragging.node.position !== 'object') {
        graphState.dragging.node.position = { x: 0, y: 0 };
      }
      graphState.dragging.node.position.x = x;
      graphState.dragging.node.position.y = y;
      renderGraph();
    }
  }
  
  function handleCanvasMouseUp(e) {
    if (graphState.dragging.active) {
      if (graphState.dragging.node) {
        // Save position
        saveNodePosition(graphState.dragging.node.id, graphState.dragging.node.position);
      }
      graphState.dragging = { node: null, offsetX: 0, offsetY: 0, active: false };
      canvas.style.cursor = 'default';
    }
    
    if (graphState.connecting.from) {
      // Cancel connection
      graphState.connecting.from = null;
      graphState.connecting.fromPort = null;
      canvas.style.cursor = 'default';
    }
  }
  
  function handleCanvasDoubleClick(e) {
    const nodeElement = e.target.closest('.graph-node');
    if (nodeElement) {
      const nodeId = nodeElement.dataset.nodeId;
      if (confirm(`Delete node '${nodeId}'?`)) {
        deleteNode(nodeId);
      }
    }
  }
  
  // API calls
  async function saveNodePosition(nodeId, position) {
    try {
      await fetch(`${API_BASE}/graph/layout`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          positions: {
            [nodeId]: position
          }
        })
      });
    } catch (error) {
      console.error('Failed to save position:', error);
    }
  }
  
  async function saveLayout() {
    const positions = {};
    graphState.nodes.forEach(node => {
      if (node.position) {
        positions[node.id] = node.position;
      }
    });
    
    try {
      await fetch(`${API_BASE}/graph/layout`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions })
      });
      alert('Layout saved!');
    } catch (error) {
      console.error('Failed to save layout:', error);
      alert('Failed to save layout.');
    }
  }
  
  async function createConnection(from, to) {
    try {
      const response = await fetch(`${API_BASE}/graph/connections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: from, to: to })
      });
      
      if (response.ok) {
        await loadGraphState();
      } else {
        const error = await response.json();
        alert(`Failed to create connection: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to create connection:', error);
      alert('Failed to create connection.');
    }
  }
  
  async function deleteConnection(from, to) {
    try {
      const response = await fetch(`${API_BASE}/graph/connections`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: from, to: to })
      });
      
      if (response.ok) {
        await loadGraphState();
      } else {
        const error = await response.json();
        alert(`Failed to delete connection: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to delete connection:', error);
    }
  }
  
  async function deleteNode(nodeId) {
    try {
      const response = await fetch(`${API_BASE}/graph/nodes/${nodeId}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        await loadGraphState();
      } else {
        const error = await response.json();
        alert(`Failed to delete node: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to delete node:', error);
    }
  }
  
  // Initialize when DOM is ready
  function tryInit() {
    if (document.getElementById('graph-canvas')) {
      initGraphEditor();
    } else {
      // Retry after a short delay
      setTimeout(tryInit, 100);
    }
  }
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInit);
  } else {
    tryInit();
  }
})();

