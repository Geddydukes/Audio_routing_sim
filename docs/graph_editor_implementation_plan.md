# 🎨 Visual Graph Editor - Implementation Plan

## Overview
Add a drag-and-drop visual graph editor to the dashboard where users can:
- Create nodes by dragging from a palette
- Connect nodes by dragging from output to input
- Move nodes around the canvas
- Delete nodes and connections
- See real-time updates as the graph changes

---

## Architecture

### Frontend
- **Library**: Use React.js or vanilla JS with a canvas library (recommend: React Flow or Cytoscape.js, or custom with SVG)
- **State**: Graph state (nodes, connections, positions) synced with backend
- **Communication**: WebSocket for real-time updates + REST API for graph operations

### Backend
- **New Endpoints**: 
  - `POST /api/graph/nodes` - Add node
  - `DELETE /api/graph/nodes/{id}` - Remove node
  - `POST /api/graph/connections` - Add connection
  - `DELETE /api/graph/connections` - Remove connection
  - `PUT /api/graph/layout` - Update node positions
  - `GET /api/graph/current` - Get current graph state with positions

---

## Phase 1: Backend API (2-3 days)

### Step 1.1: Extend Graph Engine to Support Layout
**File**: `src/aers/core/graph_engine.py`

```python
# Add to GraphEngine class:
def __init__(self, ...):
    # ... existing code ...
    self.node_positions: Dict[str, Tuple[float, float]] = {}  # node_id -> (x, y)
    self.node_layout_version: int = 0

def set_node_position(self, node_id: str, x: float, y: float) -> None:
    """Update node position in layout."""
    self.node_positions[node_id] = (x, y)
    self.node_layout_version += 1

def get_graph_state(self) -> Dict[str, Any]:
    """Get complete graph state including layout."""
    return {
        "nodes": [
            {
                "id": node_id,
                "name": node.name,
                "kind": node.__class__.__name__,
                "position": self.node_positions.get(node_id, (0, 0)),
                "inputs": len(node.inputs) if hasattr(node, 'inputs') else 0,
                "outputs": 1,  # All nodes have one output
            }
            for node_id, node in self.nodes.items()
        ],
        "connections": [
            {"from": conn.src, "to": conn.dst}
            for conn in self.connections
        ],
        "layout_version": self.node_layout_version,
    }
```

### Step 1.2: Add Graph Management Endpoints
**File**: `src/aers/ui/server.py`

```python
# Add new endpoints:

@app.get("/api/graph/current")
async def get_current_graph() -> JSONResponse:
    """Get current graph state with positions."""
    global _current_engine
    if not _current_engine:
        return JSONResponse({"nodes": [], "connections": []})
    return JSONResponse(_current_engine.get_graph_state())

@app.post("/api/graph/nodes")
async def add_node(request: Request) -> JSONResponse:
    """Add a new node to the graph."""
    global _current_engine, _simulation_task, _current_config_path
    data = await request.json()
    
    node_id = data.get("id")
    node_kind = data.get("kind")
    x = data.get("x", 0)
    y = data.get("y", 0)
    params = data.get("params", {})
    
    # Validate
    if not node_id or not node_kind:
        raise HTTPException(400, "Missing id or kind")
    
    # Add to current config
    # ... implementation ...
    
    # Restart simulation
    # ... implementation ...
    
    return JSONResponse({"success": True, "node_id": node_id})

@app.delete("/api/graph/nodes/{node_id}")
async def remove_node(node_id: str) -> JSONResponse:
    """Remove a node from the graph."""
    # ... implementation ...
    return JSONResponse({"success": True})

@app.post("/api/graph/connections")
async def add_connection(request: Request) -> JSONResponse:
    """Add a connection between nodes."""
    data = await request.json()
    src = data.get("from")
    dst = data.get("to")
    # ... implementation ...
    return JSONResponse({"success": True})

@app.delete("/api/graph/connections")
async def remove_connection(request: Request) -> JSONResponse:
    """Remove a connection."""
    data = await request.json()
    src = data.get("from")
    dst = data.get("to")
    # ... implementation ...
    return JSONResponse({"success": True})

@app.put("/api/graph/layout")
async def update_layout(request: Request) -> JSONResponse:
    """Update node positions."""
    global _current_engine
    data = await request.json()
    positions = data.get("positions", {})
    
    for node_id, pos in positions.items():
        _current_engine.set_node_position(node_id, pos["x"], pos["y"])
    
    return JSONResponse({"success": True})
```

### Step 1.3: Update Config Loader to Support Positions
**File**: `src/aers/utils/config_loader.py`

```python
# Extend RoutingConfig:
@dataclass(frozen=True)
class RoutingConfig:
    # ... existing fields ...
    node_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)

# In load_routing_config:
node_positions = {}
for node_spec in node_specs:
    node_id = node_spec.get("id")
    if "position" in node_spec:
        node_positions[node_id] = tuple(node_spec["position"])

return RoutingConfig(
    # ... existing ...
    node_positions=node_positions,
)
```

---

## Phase 2: Frontend Graph Editor (4-5 days)

### Step 2.1: Choose Library & Setup
**Option A: React Flow** (Recommended - easiest)
- Install: `npm install reactflow`
- Pros: Built-in drag-drop, connections, zoom, pan
- Cons: Requires React setup

**Option B: Cytoscape.js** (Good alternative)
- Install: `npm install cytoscape`
- Pros: Powerful, good for complex graphs
- Cons: More complex API

**Option C: Custom SVG** (Most control)
- Use vanilla JS with SVG
- Pros: Full control, no dependencies
- Cons: More code to write

**Recommendation**: Start with React Flow for speed, or custom SVG if you want to keep it vanilla JS.

### Step 2.2: Create Graph Editor Component
**File**: `ui/dashboard/graph-editor.html` (new file)

```html
<!DOCTYPE html>
<html>
<head>
    <title>AERS Graph Editor</title>
    <link rel="stylesheet" href="graph-editor.css">
</head>
<body>
    <div id="graph-editor-app">
        <!-- Node Palette -->
        <div class="node-palette">
            <h3>Nodes</h3>
            <div class="palette-item" data-kind="sine">Sine Source</div>
            <div class="palette-item" data-kind="gain">Gain</div>
            <div class="palette-item" data-kind="eq">EQ</div>
            <div class="palette-item" data-kind="delay">Delay</div>
            <div class="palette-item" data-kind="passthrough">Passthrough</div>
        </div>
        
        <!-- Canvas -->
        <div class="graph-canvas-container">
            <svg id="graph-canvas" width="1200" height="800">
                <!-- Nodes and connections rendered here -->
            </svg>
        </div>
        
        <!-- Controls -->
        <div class="graph-controls">
            <button id="save-layout-btn">Save Layout</button>
            <button id="reset-layout-btn">Reset Layout</button>
        </div>
    </div>
    
    <script src="graph-editor.js"></script>
</body>
</html>
```

### Step 2.3: Implement Graph Editor JavaScript
**File**: `ui/dashboard/graph-editor.js` (new file)

```javascript
// Graph Editor State
let graphState = {
    nodes: [],
    connections: [],
    selectedNode: null,
    dragging: false,
    connecting: { from: null, to: null }
};

// Initialize
async function initGraphEditor() {
    await loadGraphState();
    renderGraph();
    setupEventListeners();
}

// Load current graph from server
async function loadGraphState() {
    const response = await fetch('http://localhost:8000/api/graph/current');
    const data = await response.json();
    graphState.nodes = data.nodes || [];
    graphState.connections = data.connections || [];
}

// Render graph to SVG
function renderGraph() {
    const svg = document.getElementById('graph-canvas');
    svg.innerHTML = ''; // Clear
    
    // Render connections first (so they appear behind nodes)
    graphState.connections.forEach(conn => {
        const fromNode = graphState.nodes.find(n => n.id === conn.from);
        const toNode = graphState.nodes.find(n => n.id === conn.to);
        if (fromNode && toNode) {
            drawConnection(svg, fromNode, toNode);
        }
    });
    
    // Render nodes
    graphState.nodes.forEach(node => {
        drawNode(svg, node);
    });
}

// Draw a node
function drawNode(svg, node) {
    const [x, y] = node.position || [100, 100];
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.setAttribute('class', 'graph-node');
    g.setAttribute('data-node-id', node.id);
    g.setAttribute('transform', `translate(${x}, ${y})`);
    
    // Node rectangle
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('width', '120');
    rect.setAttribute('height', '60');
    rect.setAttribute('rx', '5');
    rect.setAttribute('class', 'node-box');
    g.appendChild(rect);
    
    // Node label
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', '60');
    text.setAttribute('y', '35');
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('class', 'node-label');
    text.textContent = node.name;
    g.appendChild(text);
    
    // Input port (left side)
    const inputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    inputPort.setAttribute('cx', '0');
    inputPort.setAttribute('cy', '30');
    inputPort.setAttribute('r', '5');
    inputPort.setAttribute('class', 'port port-input');
    g.appendChild(inputPort);
    
    // Output port (right side)
    const outputPort = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    outputPort.setAttribute('cx', '120');
    outputPort.setAttribute('cy', '30');
    outputPort.setAttribute('r', '5');
    outputPort.setAttribute('class', 'port port-output');
    g.appendChild(outputPort);
    
    svg.appendChild(g);
}

// Draw connection line
function drawConnection(svg, fromNode, toNode) {
    const [x1, y1] = fromNode.position || [100, 100];
    const [x2, y2] = toNode.position || [200, 200];
    
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    const path = `M ${x1 + 120} ${y1 + 30} L ${x2} ${y2 + 30}`;
    line.setAttribute('d', path);
    line.setAttribute('class', 'connection-line');
    svg.appendChild(line);
}

// Setup event listeners
function setupEventListeners() {
    // Palette drag
    document.querySelectorAll('.palette-item').forEach(item => {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('kind', item.dataset.kind);
        });
    });
    
    // Canvas drop
    const canvas = document.getElementById('graph-canvas');
    canvas.addEventListener('dragover', (e) => e.preventDefault());
    canvas.addEventListener('drop', handleCanvasDrop);
    
    // Node drag
    canvas.addEventListener('mousedown', handleNodeMouseDown);
    canvas.addEventListener('mousemove', handleNodeMouseMove);
    canvas.addEventListener('mouseup', handleNodeMouseUp);
    
    // Connection creation
    canvas.addEventListener('mousedown', handlePortMouseDown);
}

// Handle dropping node from palette
async function handleCanvasDrop(e) {
    e.preventDefault();
    const kind = e.dataTransfer.getData('kind');
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Create node via API
    const response = await fetch('http://localhost:8000/api/graph/nodes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            id: `node_${Date.now()}`,
            kind: kind,
            x: x,
            y: y,
            params: {}
        })
    });
    
    if (response.ok) {
        await loadGraphState();
        renderGraph();
    }
}

// Handle node dragging
let dragState = { node: null, offsetX: 0, offsetY: 0 };

function handleNodeMouseDown(e) {
    const nodeElement = e.target.closest('.graph-node');
    if (!nodeElement) return;
    
    const nodeId = nodeElement.dataset.nodeId;
    const node = graphState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    dragState.node = node;
    const [nodeX, nodeY] = node.position || [0, 0];
    dragState.offsetX = e.clientX - nodeX;
    dragState.offsetY = e.clientY - nodeY;
    dragState.dragging = true;
}

function handleNodeMouseMove(e) {
    if (!dragState.dragging || !dragState.node) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - dragState.offsetX;
    const y = e.clientY - rect.top - dragState.offsetY;
    
    dragState.node.position = [x, y];
    renderGraph();
}

function handleNodeMouseUp(e) {
    if (dragState.dragging && dragState.node) {
        // Save position to server
        saveNodePosition(dragState.node.id, dragState.node.position);
    }
    dragState = { node: null, offsetX: 0, offsetY: 0, dragging: false };
}

async function saveNodePosition(nodeId, position) {
    await fetch('http://localhost:8000/api/graph/layout', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            positions: {
                [nodeId]: { x: position[0], y: position[1] }
            }
        })
    });
}

// Handle connection creation
function handlePortMouseDown(e) {
    const port = e.target.closest('.port');
    if (!port) return;
    
    const nodeElement = port.closest('.graph-node');
    const nodeId = nodeElement.dataset.nodeId;
    const isOutput = port.classList.contains('port-output');
    
    if (isOutput) {
        graphState.connecting.from = nodeId;
    } else {
        if (graphState.connecting.from) {
            // Complete connection
            createConnection(graphState.connecting.from, nodeId);
            graphState.connecting.from = null;
        }
    }
}

async function createConnection(from, to) {
    const response = await fetch('http://localhost:8000/api/graph/connections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ from: from, to: to })
    });
    
    if (response.ok) {
        await loadGraphState();
        renderGraph();
    }
}

// Initialize on load
initGraphEditor();
```

### Step 2.4: Add Graph Editor Styles
**File**: `ui/dashboard/graph-editor.css` (new file)

```css
#graph-editor-app {
    display: grid;
    grid-template-columns: 200px 1fr;
    grid-template-rows: 1fr 60px;
    height: 100vh;
    background: #020617;
    color: #f9fafb;
}

.node-palette {
    grid-column: 1;
    grid-row: 1 / -1;
    background: #030712;
    border-right: 1px solid #1f2937;
    padding: 1rem;
}

.palette-item {
    padding: 0.75rem;
    margin: 0.5rem 0;
    background: #1f2937;
    border-radius: 0.375rem;
    cursor: grab;
    user-select: none;
}

.palette-item:active {
    cursor: grabbing;
}

.graph-canvas-container {
    grid-column: 2;
    grid-row: 1;
    overflow: auto;
    background: #050608;
}

#graph-canvas {
    width: 100%;
    height: 100%;
}

.graph-node {
    cursor: move;
}

.node-box {
    fill: #1f2937;
    stroke: #4CAF50;
    stroke-width: 2;
}

.node-box:hover {
    fill: #374151;
}

.node-label {
    fill: #f9fafb;
    font-size: 12px;
    font-family: system-ui;
}

.port {
    fill: #6b7280;
    cursor: crosshair;
}

.port:hover {
    fill: #4CAF50;
}

.connection-line {
    stroke: #4CAF50;
    stroke-width: 2;
    fill: none;
    marker-end: url(#arrowhead);
}

.graph-controls {
    grid-column: 2;
    grid-row: 2;
    padding: 1rem;
    background: #030712;
    border-top: 1px solid #1f2937;
}
```

---

## Phase 3: Integration (1-2 days)

### Step 3.1: Add Graph Editor Tab to Dashboard
**File**: `ui/dashboard/index.html`

```html
<!-- Add tab navigation -->
<div class="tabs">
    <button class="tab-btn active" data-tab="metrics">Metrics</button>
    <button class="tab-btn" data-tab="graph">Graph Editor</button>
</div>

<!-- Add graph editor iframe or embed -->
<div id="graph-editor-tab" class="tab-content" style="display: none;">
    <iframe src="graph-editor.html" style="width: 100%; height: 800px; border: none;"></iframe>
</div>
```

### Step 3.2: Sync Graph Changes with Metrics
**File**: `ui/dashboard/app.js`

```javascript
// Listen for graph changes and reload metrics
function setupGraphSync() {
    // Poll for graph changes or use WebSocket
    setInterval(async () => {
        const response = await fetch('http://localhost:8000/api/graph/current');
        const data = await response.json();
        // Update metrics if graph changed
    }, 1000);
}
```

---

## Phase 4: Advanced Features (Optional, 2-3 days)

### Step 4.1: Auto-Layout
- Implement force-directed layout algorithm
- Button to auto-arrange nodes
- Save/restore layout

### Step 4.2: Node Configuration Panel
- Click node to show properties
- Edit node parameters in real-time
- Live preview of changes

### Step 4.3: Connection Validation
- Prevent cycles (DAG enforcement)
- Validate node types can connect
- Show error messages

### Step 4.4: Undo/Redo
- History stack for graph operations
- Keyboard shortcuts (Ctrl+Z, Ctrl+Y)

---

## Testing Checklist

- [ ] Can drag node from palette to canvas
- [ ] Can move nodes around canvas
- [ ] Can create connections between nodes
- [ ] Can delete nodes
- [ ] Can delete connections
- [ ] Layout persists after page refresh
- [ ] Graph changes trigger simulation restart
- [ ] Real-time metrics update with graph changes
- [ ] Prevents invalid connections (cycles, wrong types)
- [ ] Works on mobile/tablet (responsive)

---

## File Structure

```
ui/dashboard/
├── index.html (existing - add tab)
├── app.js (existing - add graph sync)
├── styles.css (existing - add tab styles)
├── graph-editor.html (new)
├── graph-editor.js (new)
└── graph-editor.css (new)

src/aers/
├── ui/server.py (add graph endpoints)
├── core/graph_engine.py (add layout support)
└── utils/config_loader.py (add position loading)
```

---

## Timeline Estimate

- **Phase 1 (Backend)**: 2-3 days
- **Phase 2 (Frontend)**: 4-5 days
- **Phase 3 (Integration)**: 1-2 days
- **Phase 4 (Advanced)**: 2-3 days (optional)

**Total**: 7-10 days for basic version, 9-13 days with advanced features

---

## Next Steps

1. Start with Phase 1 - Backend API
2. Test endpoints with curl/Postman
3. Build Phase 2 - Frontend (start simple, add features incrementally)
4. Integrate with existing dashboard
5. Add polish and error handling

