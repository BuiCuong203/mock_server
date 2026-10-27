class WebDashboard:
    @classmethod
    def get_html(cls) -> str:
        return """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cloud Mock Server - Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #0b0f19;
      --bg-surface: #111827;
      --bg-surface-elevated: #1f2937;
      --bg-surface-hover: #283548;
      --border-subtle: #1e293b;
      --border-focus: #3b82f6;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --primary: #3b82f6;
      --primary-glow: rgba(59, 130, 246, 0.25);
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --purple: #8b5cf6;
      --cyan: #06b6d4;
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 16px;
      --font-sans: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-base);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Header */
    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand-icon {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #3b82f6, #8b5cf6);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      box-shadow: 0 0 16px var(--primary-glow);
    }
    .brand-title {
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #ffffff, #93c5fd);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-badge {
      font-size: 0.7rem;
      background: var(--bg-surface-elevated);
      color: var(--primary);
      padding: 0.2rem 0.5rem;
      border-radius: 9999px;
      border: 1px solid var(--border-subtle);
      font-family: var(--font-mono);
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .scenario-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      padding: 0.4rem 0.8rem;
      border-radius: var(--radius-md);
      font-size: 0.85rem;
    }
    .scenario-pill select {
      background: transparent;
      border: none;
      color: var(--text-main);
      font-family: var(--font-sans);
      font-weight: 600;
      font-size: 0.85rem;
      outline: none;
      cursor: pointer;
    }
    .scenario-pill select option {
      background: var(--bg-surface-elevated);
      color: var(--text-main);
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: var(--bg-surface-elevated);
      color: var(--text-main);
      border: 1px solid var(--border-subtle);
      padding: 0.45rem 0.9rem;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
    }
    .btn:hover {
      background: var(--bg-surface-hover);
      border-color: var(--border-focus);
    }
    .btn-primary {
      background: linear-gradient(135deg, #2563eb, #3b82f6);
      border-color: transparent;
      color: white;
      box-shadow: 0 0 12px var(--primary-glow);
    }
    .btn-primary:hover {
      background: linear-gradient(135deg, #1d4ed8, #2563eb);
    }
    .btn-danger {
      color: var(--danger);
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.15);
      border-color: var(--danger);
    }

    /* Tabs */
    .tabs-bar {
      background: var(--bg-surface);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      padding: 0 2rem;
      gap: 1.5rem;
    }
    .tab-btn {
      padding: 0.85rem 0;
      background: none;
      border: none;
      color: var(--text-muted);
      font-family: var(--font-sans);
      font-weight: 500;
      font-size: 0.9rem;
      cursor: pointer;
      position: relative;
      transition: color 0.2s;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .tab-btn * { pointer-events: none; }
    .tab-btn:hover { color: var(--text-main); }
    .tab-btn.active {
      color: var(--primary);
      font-weight: 600;
    }
    .tab-btn.active::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 0;
      right: 0;
      height: 2px;
      background: var(--primary);
      box-shadow: 0 0 8px var(--primary);
    }

    /* Content Area */
    main {
      flex: 1;
      padding: 1.5rem 2rem;
      max-width: 1400px;
      margin: 0 auto;
      width: 100%;
    }

    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s ease-in; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    /* Overview Stats Bar */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .stat-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      position: relative;
      overflow: hidden;
    }
    .stat-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
      background: linear-gradient(90deg, var(--primary), var(--purple));
    }
    .stat-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-dim);
      font-weight: 600;
    }
    .stat-value {
      font-size: 1.6rem;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-main);
    }
    .stat-sub {
      font-size: 0.8rem;
      color: var(--text-muted);
    }

    /* Filter & Controls */
    .controls-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 1rem;
      flex-wrap: wrap;
    }
    .search-input {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 0.5rem 0.85rem;
      color: var(--text-main);
      font-family: var(--font-sans);
      font-size: 0.85rem;
      min-width: 260px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-input:focus {
      border-color: var(--border-focus);
    }

    /* Table Styles */
    .table-container {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
      text-align: left;
    }
    th {
      background: var(--bg-surface-elevated);
      padding: 0.75rem 1rem;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-subtle);
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.05em;
    }
    td {
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border-subtle);
      color: var(--text-main);
    }
    tr:last-child td { border-bottom: none; }
    tr.selected-log-row td {
      background: rgba(59, 130, 246, 0.22) !important;
      border-top: 1px solid var(--primary) !important;
      border-bottom: 1px solid var(--primary) !important;
    }
    tr.selected-log-row td:first-child {
      border-left: 3px solid var(--primary) !important;
    }
    .split-inspector-container {
      display: grid;
      grid-template-columns: 1fr 1.15fr;
      gap: 1.25rem;
      align-items: start;
    }
    @media (max-width: 1200px) {
      .split-inspector-container {
        grid-template-columns: 1fr;
      }
    }
    .inspector-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      position: sticky;
      top: 5rem;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
    }
    .inspector-card-header {
      background: var(--bg-surface-elevated);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0.85rem 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.6rem;
    }
    .sub-tabs-bar {
      display: flex;
      gap: 0.4rem;
      background: rgba(17, 24, 39, 0.95);
      padding: 0.4rem 1rem;
      border-bottom: 1px solid var(--border-subtle);
    }
    .sub-tab-btn {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      padding: 0.35rem 0.75rem;
      font-size: 0.8rem;
      font-weight: 500;
      cursor: pointer;
      border-radius: var(--radius-sm);
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }
    .sub-tab-btn:hover {
      color: var(--text-main);
      background: var(--bg-surface-elevated);
    }
    .sub-tab-btn.active {
      background: var(--primary);
      color: #fff;
      font-weight: 600;
      box-shadow: 0 0 12px var(--primary-glow);
    }
    .inspector-body {
      padding: 1.25rem;
      max-height: 64vh;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .btn-sm {
      padding: 0.25rem 0.6rem;
      font-size: 0.75rem;
    }
    .params-table {
      width: 100%;
      border-collapse: collapse;
      font-family: var(--font-mono);
      font-size: 0.78rem;
      background: #080c14;
      border-radius: var(--radius-sm);
      overflow: hidden;
      border: 1px solid var(--border-subtle);
    }
    .params-table td {
      padding: 0.4rem 0.75rem;
      border-bottom: 1px solid var(--border-subtle);
    }
    .params-table td.param-key {
      color: var(--cyan);
      font-weight: 600;
      width: 35%;
      border-right: 1px solid var(--border-subtle);
    }
    .params-table td.param-val {
      color: #cbd5e1;
      word-break: break-all;
    }

    /* Badges */
    .badge {
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: var(--radius-sm);
      font-weight: 600;
      font-size: 0.75rem;
      font-family: var(--font-mono);
    }
    .badge-method-get { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-method-post { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .badge-method-connect { background: rgba(139, 92, 246, 0.15); color: #c084fc; }
    .badge-status-2xx { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-status-4xx { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
    .badge-status-5xx { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    .badge-rule { background: var(--bg-surface-elevated); color: var(--text-muted); font-size: 0.7rem; }
    .badge-cat-rest_api { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-cat-azure { background: rgba(14, 165, 233, 0.15); color: #38bdf8; border: 1px solid rgba(14, 165, 233, 0.3); }
    .badge-cat-defender { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-cat-m365 { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-cat-cloudwatch { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-cat-aws_s3sqs { background: rgba(249, 115, 22, 0.15); color: #fb923c; border: 1px solid rgba(249, 115, 22, 0.3); }
    .badge-cat-generic, .badge-cat-custom { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }

    .form-section {
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1rem 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }
    .form-section-title {
      font-size: 0.8rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--primary);
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.25rem;
    }
    .modal-box-large { max-width: 960px !important; }

    /* Modal / Inspector Drawer */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 1rem;
    }
    .modal-overlay.open { display: flex; animation: fadeIn 0.15s ease-out; }
    .modal-box {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 800px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    }
    .modal-header {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .modal-title { font-size: 1.1rem; font-weight: 600; }
    .modal-body {
      padding: 1.5rem;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }
    .code-block {
      background: #080c14;
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 0.85rem;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      color: #cbd5e1;
      white-space: pre-wrap;
      word-break: break-all;
      max-height: 280px;
      overflow-y: auto;
    }

    /* Scenario Cards Grid */
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 1.25rem;
    }
    .scenario-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 1rem;
      transition: all 0.2s ease;
    }
    .scenario-card:hover {
      border-color: var(--border-focus);
      transform: translateY(-2px);
    }
    .scenario-card.active-card {
      border-color: var(--primary);
      box-shadow: 0 0 16px var(--primary-glow);
      background: linear-gradient(180deg, rgba(59, 130, 246, 0.05), transparent);
    }

    /* Form Controls */
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }
    .form-group label {
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
    }
    .form-control {
      background: #080c14;
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 0.6rem 0.85rem;
      color: var(--text-main);
      font-family: var(--font-sans);
      font-size: 0.85rem;
      outline: none;
    }
    .form-control:focus { border-color: var(--border-focus); }
    textarea.form-control {
      font-family: var(--font-mono);
      font-size: 0.8rem;
      resize: vertical;
      min-height: 120px;
    }

    /* Live pulse dot */
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: var(--success);
      border-radius: 50%;
      display: inline-block;
      box-shadow: 0 0 8px var(--success);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    /* ===== Mock Sender ===== */
    .sender-layout {
      display: grid;
      grid-template-columns: minmax(340px, 460px) 1fr;
      gap: 1.25rem;
      align-items: start;
    }
    @media (max-width: 980px) { .sender-layout { grid-template-columns: 1fr; } }
    .sender-panel {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .sender-panel h3 { font-size: 1rem; font-weight: 600; }
    .sender-panel .form-control { width: 100%; min-width: 0; }
    .sender-layout > *, .sender-row > *, .sender-row-3 > * { min-width: 0; }
    @media (max-width: 520px) { .sender-row, .sender-row-3 { grid-template-columns: 1fr; } }
    .sender-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
    .sender-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; }
    .type-switch { display: flex; gap: 0.4rem; flex-wrap: wrap; }
    .type-switch button {
      background: var(--bg-surface-elevated);
      color: var(--text-muted);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 0.4rem 0.9rem;
      font-family: var(--font-sans);
      font-size: 0.85rem;
      cursor: pointer;
    }
    .type-switch button.active { color: var(--text-main); border-color: var(--primary); box-shadow: 0 0 10px var(--primary-glow); }
    .type-switch button:disabled { opacity: 0.45; cursor: not-allowed; }
    .sender-hint { font-size: 0.75rem; color: var(--text-dim); line-height: 1.5; }
    .sender-hint code { font-family: var(--font-mono); color: #93c5fd; }
    .sender-actions { display: flex; gap: 0.6rem; flex-wrap: wrap; }
    .sender-msg { font-size: 0.8rem; min-height: 1.1rem; }
    .sender-msg.err { color: var(--danger); }
    .sender-msg.ok { color: var(--success); }
    .badge-job-running { background: rgba(16, 185, 129, 0.15); color: #34d399; }
    .badge-job-done { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
    .badge-job-stopped { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }
    .badge-job-error { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    .job-last { font-family: var(--font-mono); font-size: 0.72rem; color: var(--text-dim); max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .sender-side { display: flex; flex-direction: column; gap: 1.25rem; }
    .field-help { font-size: 0.72rem; color: var(--text-dim); line-height: 1.45; }
    .sender-panel details { border-top: 1px solid var(--border-subtle); padding-top: 0.75rem; }
    .sender-panel summary { cursor: pointer; font-size: 0.85rem; color: var(--text-muted); font-weight: 500; }
    .sender-panel details[open] summary { margin-bottom: 0.85rem; }
    .adv-body { display: flex; flex-direction: column; gap: 0.85rem; }
    .check-line { display: flex; align-items: flex-start; gap: 0.45rem; font-size: 0.82rem; color: var(--text-main); }
    .check-line input { margin-top: 0.2rem; }
    .pv-title { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; font-size: 0.8rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .pv-summary { font-size: 0.9rem; color: var(--text-main); line-height: 1.5; }
    .pv-code { background: #080c14; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 0.75rem; font-family: var(--font-mono); font-size: 0.78rem; color: #cbd5e1; white-space: pre-wrap; word-break: break-all; max-height: 220px; overflow-y: auto; }
    .pv-nl { color: var(--warning); }
    .pv-meta { color: var(--text-dim); font-size: 0.7rem; }
    .pv-notes { margin: 0; padding-left: 1.1rem; font-size: 0.75rem; color: var(--warning); line-height: 1.5; }
    .sender-modes { display: flex; gap: 0.4rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .sender-modes .sub-tab-btn { border-color: var(--border-subtle); font-family: var(--font-sans); font-size: 0.85rem; padding: 0.45rem 0.95rem; }
    .sender-modes .sub-tab-btn small { font-weight: 400; opacity: 0.75; }
    .copy-btn { padding: 0.15rem 0.55rem !important; font-size: 0.72rem !important; text-transform: none; letter-spacing: 0; }
  </style>
</head>
<body>

  <!-- Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="brand-title">Cloud Mock Server</span>
          <span class="brand-badge">PORT 8081</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-dim); display: flex; align-items: center; gap: 0.4rem; margin-top: 0.15rem;">
          <span class="pulse-dot"></span> Online &bull; 6 Cloud Sources Active
        </div>
      </div>
    </div>

    <div class="header-actions">
      <div class="scenario-pill">
        <span style="color: var(--text-dim); font-size: 0.8rem;">🎭 Kịch bản:</span>
        <select id="quickScenarioSelect" onchange="switchScenario(this.value)">
          <option value="default">default (Đang tải...)</option>
        </select>
      </div>

      <button class="btn btn-primary" onclick="openNewRuleModal()">+ Thêm Rule Mock</button>
      <button class="btn" onclick="fetchScenarios(true)">🔄 Nạp lại File</button>
      <button class="btn btn-danger" onclick="clearLogs()">🗑️ Xóa Logs</button>
    </div>
  </header>

  <!-- Tabs Bar -->
  <nav class="tabs-bar">
    <button class="tab-btn active" id="tabBtn-inspector" data-tab="inspector" onclick="setTab('inspector', this)">📡 Request Inspector (<span id="reqCount">0</span>)</button>
    <button class="tab-btn" id="tabBtn-scenarios" data-tab="scenarios" onclick="setTab('scenarios', this)">🎭 Kịch Bản & Presets</button>
    <button class="tab-btn" id="tabBtn-rules" data-tab="rules" onclick="setTab('rules', this)">🛠️ Quản Lý Mock Rules (<span id="rulesCount">0</span>)</button>
    <button class="tab-btn" id="tabBtn-sender" data-tab="sender" onclick="setTab('sender', this)">📤 Mock Sender (<span id="senderRunningCount">0</span>)</button>
    <button class="tab-btn" id="tabBtn-pubsub" data-tab="pubsub" onclick="setTab('pubsub', this)">☁️ GCP Pub/Sub</button>
  </nav>

  <!-- Main Content Area -->
  <main>
    <!-- TAB 1: REQUEST INSPECTOR -->
    <section id="tab-inspector" class="tab-content active">
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-label">Tổng Request Đã Nhận</span>
          <span class="stat-value" id="statTotalReq">0</span>
          <span class="stat-sub">Tự động cập nhật mỗi 2s</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Kịch Bản Hiện Tại</span>
          <span class="stat-value" id="statActiveScenario" style="font-size: 1.3rem; color: #60a5fa;">default</span>
          <span class="stat-sub">Có thể chuyển đổi tức thì</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Số Rule Đang Kích Hoạt</span>
          <span class="stat-value" id="statActiveRules">0</span>
          <span class="stat-sub">Custom overrides + Scenario</span>
        </div>
        <div class="stat-card">
          <span class="stat-label">Server Uptime</span>
          <span class="stat-value" id="statUptime">0s</span>
          <span class="stat-sub">Thread-safe HTTPS Proxy</span>
        </div>
      </div>

      <div class="controls-row">
        <input type="text" id="logSearchInput" class="search-input" placeholder="🔍 Tìm theo path, host, rule..." oninput="filterLogs()">
        <div style="display: flex; gap: 0.5rem;">
          <select id="statusFilter" class="form-control" style="width: 140px;" onchange="filterLogs()">
            <option value="">Tất cả Status</option>
            <option value="200">200 OK</option>
            <option value="401">401 Auth Fail</option>
            <option value="404">404 Not Found</option>
            <option value="429">429 Rate Limit</option>
            <option value="500">500 Server Error</option>
          </select>
        </div>
      </div>

      <div class="split-inspector-container">
        <!-- Cột Trái: Bảng danh sách các Request -->
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th style="width: 50px;">ID</th>
                  <th style="width: 75px;">Giờ</th>
                  <th style="width: 70px;">Method</th>
                  <th>Path & Host</th>
                  <th style="width: 75px;">Status</th>
                  <th style="width: 70px; text-align: center;">Xem</th>
                </tr>
              </thead>
              <tbody id="logsTableBody">
                <tr>
                  <td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Chưa có request nào từ Shipper. Hãy khởi động Shipper!</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Cột Phải: Panel Chi Tiết Request & Response -->
        <div class="inspector-card" id="sideInspectorCard">
          <div class="inspector-card-header">
            <div style="display: flex; align-items: center; gap: 0.6rem; overflow: hidden; max-width: 65%;">
              <span id="sideMethodBadge" class="badge badge-method-get">GET</span>
              <span id="sidePathTitle" style="font-weight: 600; font-family: var(--font-mono); font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">/mock/...</span>
            </div>
            <div style="display: flex; gap: 0.4rem; align-items: center;">
              <span id="sideStatusBadge" class="badge badge-status-2xx">200</span>
              <button class="btn btn-sm" onclick="copyCurrentCurl()" title="Copy lệnh cURL">📋 cURL</button>
              <button class="btn btn-sm" onclick="openCurrentInModal()" title="Phóng to Modal">⛶</button>
            </div>
          </div>

          <div class="sub-tabs-bar">
            <button class="sub-tab-btn active" id="subtabBtn-req" onclick="setSubTab('req')">📥 Request Body & Headers</button>
            <button class="sub-tab-btn" id="subtabBtn-resp" onclick="setSubTab('resp')">📤 Response Data</button>
            <button class="sub-tab-btn" id="subtabBtn-meta" onclick="setSubTab('meta')">⚙️ Rule & Debug</button>
          </div>

          <!-- Nội dung tab 1: Request -->
          <div id="subtab-req" class="inspector-body">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600;">🌐 FULL REQUEST URL & CLIENT</label>
                <span id="sideClientIp" style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-dim);">IP: 127.0.0.1</span>
              </div>
              <div id="sideFullUrl" style="font-family: var(--font-mono); font-size: 0.8rem; background: #080c14; padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); color: #93c5fd; word-break: break-all;">-</div>
            </div>

            <div id="sideParamsGroup" style="display: none;">
              <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 0.35rem; display: block;">🔍 QUERY PARAMETERS (Bóc tách OData / Filter)</label>
              <table class="params-table" id="sideParamsTable"></table>
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600;">📥 REQUEST PAYLOAD / BODY (Từ Shipper gửi lên)</label>
                <button class="btn btn-sm" onclick="copyReqBody()">📋 Copy Body</button>
              </div>
              <div class="code-container">
                <div id="sideReqBody" class="code-block" style="max-height: 220px;">(Trống)</div>
              </div>
            </div>

            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600;">📋 REQUEST HEADERS</label>
                <button class="btn btn-sm" onclick="copyReqHeaders()">📋 Copy Headers</button>
              </div>
              <div id="sideReqHeaders" class="code-block" style="max-height: 180px;"></div>
            </div>
          </div>

          <!-- Nội dung tab 2: Response -->
          <div id="subtab-resp" class="inspector-body" style="display: none;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600;">📤 RESPONSE BODY (Dữ liệu Mock trả về Shipper)</label>
                <button class="btn btn-sm" onclick="copyRespBody()">📋 Copy Response</button>
              </div>
              <div id="sideRespBody" class="code-block" style="max-height: 320px;">(Trống)</div>
            </div>
            <div>
              <label style="color: var(--text-dim); font-size: 0.75rem; font-weight: 600; margin-bottom: 0.35rem; display: block;">📋 RESPONSE HEADERS</label>
              <div id="sideRespHeaders" class="code-block" style="max-height: 180px;"></div>
            </div>
          </div>

          <!-- Nội dung tab 3: Meta & Rule -->
          <div id="subtab-meta" class="inspector-body" style="display: none;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="stat-card" style="padding: 0.85rem;">
                <span class="stat-label">Rule Xử Lý</span>
                <span id="sideMatchedRule" style="font-size: 0.95rem; font-weight: 600; color: var(--cyan); word-break: break-all;">-</span>
              </div>
              <div class="stat-card" style="padding: 0.85rem;">
                <span class="stat-label">Thời Gian Xử Lý</span>
                <span id="sideDuration" style="font-size: 1.1rem; font-weight: 600; color: #34d399;">0ms</span>
              </div>
            </div>
            <div class="stat-card" style="padding: 0.85rem;">
              <span class="stat-label">Host Đích</span>
              <span id="sideHost" style="font-family: var(--font-mono); font-size: 0.85rem; color: #f8fafc;">localhost</span>
            </div>
            <div class="stat-card" style="padding: 0.85rem;">
              <span class="stat-label">Thời Gian Ghi Nhận</span>
              <span id="sideTimestamp" style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-muted);">-</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: SCENARIOS -->
    <section id="tab-scenarios" class="tab-content">
      <div style="margin-bottom: 1.5rem;">
        <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 0.25rem;">Quản Lý Kịch Bản Mock (Scenarios)</h2>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Chọn kịch bản phù hợp để test các tình huống lỗi mạng, rate-limit, auth fail trên CyM-Log-Shipper mà không cần đổi code.</p>
      </div>
      <div class="cards-grid" id="scenariosGrid"></div>
    </section>

    <!-- TAB 3: RULES -->
    <section id="tab-rules" class="tab-content">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h2 style="font-size: 1.35rem; font-weight: 700; margin-bottom: 0.35rem; display: flex; align-items: center; gap: 0.6rem;">
            <span>🛠️ Quản Lý Mock Rules & Endpoints</span>
            <span id="rulesActivePill" class="brand-badge" style="font-size: 0.75rem;">0 Rules</span>
          </h2>
          <p style="color: var(--text-muted); font-size: 0.85rem;">Xem chi tiết từng rule, chỉnh sửa trực tiếp đầu vào / đầu ra và lưu lại tức thì vào file JSON cấu hình.</p>
        </div>
        <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
          <button class="btn btn-primary" onclick="openNewRuleModal()">➕ Thêm Rule Mới</button>
          <button class="btn" onclick="reloadRulesFromDisk()">🔄 Nạp Lại Từ Ổ Đĩa</button>
        </div>
      </div>

      <!-- Filter Controls Bar -->
      <div class="controls-row" style="margin-bottom: 1rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;">
        <input type="text" id="ruleSearchInput" class="search-input" style="flex: 1; min-width: 260px;" placeholder="🔍 Tìm kiếm theo tên rule, path URL, method, host, file nguồn..." oninput="filterRules()">
        <select id="ruleCategoryFilter" class="form-control" style="width: 175px;" onchange="filterRules()">
          <option value="">Tất cả Nguồn Cloud</option>
          <option value="rest_api">Generic REST API</option>
          <option value="azure">Azure Poller</option>
          <option value="defender">Microsoft Defender</option>
          <option value="m365">Microsoft 365</option>
          <option value="cloudwatch">AWS CloudWatch</option>
          <option value="aws_s3sqs">AWS S3-SQS</option>
          <option value="custom">Custom Overrides</option>
        </select>
        <select id="ruleModeFilter" class="form-control" style="width: 140px;" onchange="filterRules()">
          <option value="">Tất cả Mode</option>
          <option value="all">⚡ All (Cả 2)</option>
          <option value="direct">🌐 Direct HTTP</option>
          <option value="proxy">🔒 HTTPS Proxy</option>
        </select>
        <select id="ruleStatusFilter" class="form-control" style="width: 130px;" onchange="filterRules()">
          <option value="">Status Code</option>
          <option value="200">200 OK</option>
          <option value="401">401 Auth</option>
          <option value="429">429 Rate Limit</option>
          <option value="500">500 Error</option>
        </select>
      </div>

      <div class="table-container">
        <table style="width: 100%;">
          <thead>
            <tr>
              <th style="width: 45px; text-align: center;">Bật</th>
              <th style="width: 250px;">Tên Rule & File Nguồn</th>
              <th style="width: 120px;">Nguồn Cloud</th>
              <th style="width: 85px;">Phạm Vi</th>
              <th style="width: 75px;">Method</th>
              <th>Điều Kiện Khớp (Match Criteria)</th>
              <th style="width: 140px;">Phản Hồi (Response)</th>
              <th style="width: 60px; text-align: center;">Hits</th>
              <th style="width: 110px; text-align: right;">Thao Tác</th>
            </tr>
          </thead>
          <tbody id="rulesTableBody">
            <tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 2rem;">Đang tải danh sách rules...</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- TAB 4: MOCK SENDER -->
    <section id="tab-sender" class="tab-content">
      <div style="margin-bottom: 1.25rem;">
        <h2 style="font-size: 1.35rem; font-weight: 700; margin-bottom: 0.35rem;">📤 Mock Sender</h2>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Bắn log từ mock server tới cổng nhận log của shipper (input syslog / udp / tcp / redis / beats / http). Điền <b>IP</b>, <b>cổng</b> và <b>nội dung log</b>; khung bên phải cho thấy lệnh / code tương đương và gói tin sẽ gửi.</p>
      </div>

      <div class="sender-modes" role="tablist">
        <button class="sub-tab-btn active" id="senderModeBtn-syslog" onclick="setSenderMode('syslog')">Syslog <small>(gửi nguyên văn)</small></button>
        <button class="sub-tab-btn" id="senderModeBtn-udp" onclick="setSenderMode('udp')">UDP <small>(Python logging)</small></button>
        <button class="sub-tab-btn" id="senderModeBtn-tcp" onclick="setSenderMode('tcp')">TCP <small>(Python logging)</small></button>
        <button class="sub-tab-btn" id="senderModeBtn-redis" onclick="setSenderMode('redis')">Redis <small>(đẩy vào key)</small></button>
        <button class="sub-tab-btn" id="senderModeBtn-beats" onclick="setSenderMode('beats')">Beats <small>(giả Filebeat)</small></button>
        <button class="sub-tab-btn" id="senderModeBtn-http" onclick="setSenderMode('http')">HTTP <small>(POST /log)</small></button>
      </div>

      <div class="sender-layout">
        <!-- Cấu hình -->
        <div class="sender-panel">
          <div class="form-group" id="sndTransportGroup">
            <label for="sndTransport">Giao thức *</label>
            <select id="sndTransport" class="form-control" onchange="onSenderTransportChange(); schedulePreview()">
              <option value="udp">UDP</option>
              <option value="tcp">TCP</option>
            </select>
          </div>

          <div class="sender-row">
            <div class="form-group">
              <label for="sndHost">Gửi tới IP *</label>
              <input id="sndHost" class="form-control" placeholder="vd 172.22.0.1" oninput="schedulePreview()">
              <span class="field-help" id="sndHostHelp">IP máy đang chạy shipper. Mock chạy trong Docker thì 127.0.0.1 là chính container; dùng IP gateway Docker (vd 172.22.0.1) để tới máy host.</span>
            </div>
            <div class="form-group">
              <label for="sndPort">Cổng *</label>
              <input id="sndPort" class="form-control" type="number" min="1" max="65535" value="514" oninput="schedulePreview()">
              <span class="field-help" id="sndPortHelp">Cổng của input syslog / udp / tcp trong cấu hình shipper.</span>
            </div>
          </div>

          <div class="sender-row">
            <div class="form-group">
              <label for="sndUser">User</label>
              <input id="sndUser" class="form-control" placeholder="hoangnx" oninput="schedulePreview()">
              <span class="field-help">Chèn vào log tại <code style="font-family: var(--font-mono); color: #93c5fd;">{{USER}}</code></span>
            </div>
            <div class="form-group">
              <label for="sndAction">Action</label>
              <input id="sndAction" class="form-control" placeholder="NODE_POST_INFO_1" oninput="schedulePreview()">
              <span class="field-help">Chèn vào log tại <code style="font-family: var(--font-mono); color: #93c5fd;">{{ACTION}}</code></span>
            </div>
          </div>

          <div id="sndRedisOpts" class="adv-body" style="display: none;">
            <div class="sender-row">
              <div class="form-group">
                <label for="sndRedisPassword">Mật khẩu</label>
                <input id="sndRedisPassword" class="form-control" type="password" autocomplete="off" placeholder="để trống nếu Redis không đặt mật khẩu" oninput="schedulePreview()">
              </div>
              <div class="form-group">
                <label for="sndRedisUser">Username (ACL)</label>
                <input id="sndRedisUser" class="form-control" placeholder="thường để trống" oninput="schedulePreview()">
              </div>
            </div>
            <span class="field-help">Mật khẩu chỉ dùng khi gửi: không lưu trong trình duyệt, không hiện trong lệnh mẫu hay danh sách lượt gửi.</span>
            <div class="sender-row">
              <div class="form-group">
                <label for="sndRedisKey">Key *</label>
                <input id="sndRedisKey" class="form-control" style="font-family: var(--font-mono);" placeholder="cym_logs" oninput="schedulePreview()">
                <span class="field-help">Trùng với <code style="font-family: var(--font-mono); color: #93c5fd;">key</code> của input redis trong cấu hình shipper.</span>
              </div>
              <div class="form-group">
                <label for="sndRedisDb">DB</label>
                <input id="sndRedisDb" class="form-control" type="number" min="0" max="1000" value="0" oninput="schedulePreview()">
                <span class="field-help">Trùng với <code style="font-family: var(--font-mono); color: #93c5fd;">db</code> của input redis (mặc định 0).</span>
              </div>
            </div>
            <div class="form-group">
              <label for="sndRedisCommand">Cách đẩy vào Redis</label>
              <select id="sndRedisCommand" class="form-control" onchange="schedulePreview()">
                <option value="rpush">RPUSH: thêm vào cuối LIST (shipper đọc đúng thứ tự)</option>
                <option value="lpush">LPUSH: thêm vào đầu LIST (shipper đọc ngược thứ tự)</option>
                <option value="publish">PUBLISH: gửi vào kênh Pub/Sub (input redis của shipper không đọc)</option>
              </select>
            </div>
          </div>

          <div id="sndBeatsOpts" class="adv-body" style="display: none;">
            <div class="sender-row">
              <div class="form-group">
                <label for="sndBeatsBatch">Số event mỗi batch</label>
                <input id="sndBeatsBatch" class="form-control" type="number" min="1" max="10000" value="50" oninput="schedulePreview()">
                <span class="field-help">Mỗi lượt gửi là 1 batch Lumberjack v2, mock chờ shipper ACK đủ cả batch.</span>
              </div>
              <div class="form-group" style="justify-content: center;">
                <label class="check-line"><input type="checkbox" id="sndBeatsCompress" checked onchange="schedulePreview()"> <span>Nén zlib (như Filebeat mặc định)</span></label>
                <label class="check-line"><input type="checkbox" id="sndBeatsTls" onchange="schedulePreview()"> <span>TLS (input beats có <code style="font-family: var(--font-mono); color: #93c5fd;">ssl: true</code>)</span></label>
              </div>
            </div>
          </div>

          <div id="sndHttpOpts" class="adv-body" style="display: none;">
            <div class="sender-row">
              <div class="form-group">
                <label for="sndHttpPath">Endpoint</label>
                <select id="sndHttpPath" class="form-control" onchange="schedulePreview()">
                  <option value="/log">/log: đưa vào pipeline shipper</option>
                  <option value="/data">/data: đẩy sang NATS (không ra output)</option>
                </select>
              </div>
              <div class="form-group">
                <label for="sndHttpBatch">Số log mỗi request</label>
                <input id="sndHttpBatch" class="form-control" type="number" min="1" max="10000" value="10" oninput="schedulePreview()">
              </div>
            </div>
            <div class="form-group">
              <label for="sndHttpApiKey">X-API-KEY</label>
              <input id="sndHttpApiKey" class="form-control" style="font-family: var(--font-mono);" placeholder="để trống = mock tự ký token khớp PUB_KEY của mock" oninput="schedulePreview()">
            </div>
            <details id="sndHttpSignBox" style="border: 1px solid var(--border-subtle); border-radius: 8px; padding: 0.6rem 0.75rem;">
              <summary style="cursor: pointer; font-size: 0.85rem;">🔏 Sinh token từ private key (vd <code style="font-family: var(--font-mono); color: #93c5fd;">agent.key</code>)</summary>
              <div class="form-group" style="margin-top: 0.6rem;">
                <label for="sndHttpPrivKey">Private key (PEM)</label>
                <textarea id="sndHttpPrivKey" class="form-control" style="min-height: 110px; font-family: var(--font-mono); font-size: 0.72rem;" autocomplete="off" spellcheck="false" placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"></textarea>
                <span class="field-help">Khóa cặp với PUB_KEY của collector (Consul: certificates/agent.key). Chỉ dùng để ký rồi bỏ: không lưu trong trình duyệt, không ghi xuống đĩa, không hiện ở Request Inspector.</span>
              </div>
              <div class="form-group">
                <label for="sndHttpPayload">Payload</label>
                <input id="sndHttpPayload" class="form-control" style="font-family: var(--font-mono);" value='{"agent_id":"mock-sender"}'>
                <span class="field-help">Shipper chỉ kiểm tra chữ ký, payload là gì cũng được. Cùng khóa + cùng payload luôn ra cùng một token.</span>
              </div>
              <div class="sender-actions">
                <button type="button" class="btn btn-primary" onclick="signHttpToken()">🔏 Sinh token</button>
                <button type="button" class="btn" onclick="document.getElementById('sndHttpPrivKey').value=''; setSenderMsg('Đã xóa private key khỏi form.', 'ok')">Xóa khóa</button>
              </div>
              <div id="sndHttpTokenWrap" style="display: none; flex-direction: column; gap: 0.4rem;">
                <div class="pv-title"><span>Token (header X-API-KEY)</span><button type="button" class="btn copy-btn" onclick="copySenderText('sndHttpToken')">Sao chép</button></div>
                <div id="sndHttpToken" class="pv-code" style="word-break: break-all; white-space: pre-wrap;"></div>
              </div>
              <div id="sndHttpSignResult" class="field-help" style="word-break: break-all;"></div>
            </details>
            <label class="check-line"><input type="checkbox" id="sndHttpTls" onchange="schedulePreview()"> <span>HTTPS (input http có <code style="font-family: var(--font-mono); color: #93c5fd;">tls: true</code>)</span></label>
            <div class="sender-actions">
              <button type="button" class="btn" onclick="loadHttpShipperEnv()">🔑 Lấy biến môi trường cho shipper</button>
            </div>
            <span class="field-help">Shipper phải có PUB_KEY / SSL_CERT / SSL_KEY trùng với khóa của mock thì mới chấp nhận token.</span>
          </div>

          <div id="sndLoggingOpts" class="adv-body" style="display: none;">
            <div class="sender-row">
              <div class="form-group">
                <label for="sndLevel">Mức log (level)</label>
                <select id="sndLevel" class="form-control" onchange="schedulePreview()"><option value="INFO">INFO</option></select>
              </div>
              <div class="form-group">
                <label for="sndLoggerName">Tên logger</label>
                <input id="sndLoggerName" class="form-control" placeholder="mock_sender" oninput="schedulePreview()">
              </div>
            </div>
            <div class="form-group">
              <label for="sndLogFormat">Định dạng dòng log (logging.Formatter)</label>
              <input id="sndLogFormat" class="form-control" style="font-family: var(--font-mono);" placeholder="%(asctime)s %(levelname)s %(name)s: %(message)s" oninput="schedulePreview()">
              <span class="field-help"><code style="font-family: var(--font-mono); color: #93c5fd;">%(message)s</code> = nội dung log bên dưới; <code style="font-family: var(--font-mono); color: #93c5fd;">%(asctime)s</code> thời gian, <code style="font-family: var(--font-mono); color: #93c5fd;">%(levelname)s</code> mức log, <code style="font-family: var(--font-mono); color: #93c5fd;">%(name)s</code> tên logger. Chỉ muốn gửi đúng nội dung thì để <code style="font-family: var(--font-mono); color: #93c5fd;">%(message)s</code>.</span>
            </div>
          </div>

          <div class="form-group">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;">
              <label for="sndMessage">Nội dung log *</label>
              <div style="display: flex; gap: 0.4rem;">
                <button type="button" class="btn" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;" onclick="fillDefaultSenderForm()" title="Điền lại toàn bộ form bằng cấu hình mẫu của chế độ đang chọn">⚙ Điền cấu hình mẫu</button>
                <button type="button" class="btn" style="padding: 0.2rem 0.6rem; font-size: 0.75rem;" onclick="fillDefaultSenderMessage()">Điền log mẫu</button>
              </div>
            </div>
            <textarea id="sndMessage" class="form-control" style="min-height: 140px;" placeholder="Nhập nguyên văn log, kể cả header syslog nếu cần, vd:&#10;<14>{&quot;state&quot;: &quot;success&quot;, &quot;action&quot;: &quot;NODE_POST_INFO_1&quot;}" oninput="schedulePreview()"></textarea>
            <span class="field-help" id="sndMsgHelp">Mock gửi đúng từng ký tự bạn nhập, không tự thêm header.</span>
            <label class="check-line"><input type="checkbox" id="sndSplit" checked onchange="schedulePreview()"> <span>Mỗi dòng là một log riêng (nhiều dòng thì gửi lần lượt, quay vòng)</span></label>
            <label class="check-line" id="sndNewlineGroup"><input type="checkbox" id="sndNewline" checked onchange="schedulePreview()"> <span>Thêm ký tự xuống dòng ở cuối mỗi log (giống echo; bỏ chọn = giống echo -n)</span></label>
            <span class="field-help">Có thể chèn giá trị tự sinh: <code style="font-family: var(--font-mono); color: #93c5fd;">{{USER}}</code>, <code style="font-family: var(--font-mono); color: #93c5fd;">{{ACTION}}</code> lấy từ 2 ô trên, <code style="font-family: var(--font-mono); color: #93c5fd;">{{SEQ}}</code> số thứ tự, <code style="font-family: var(--font-mono); color: #93c5fd;">{{NOW_MS}}</code> thời gian hiện tại (ms), <code style="font-family: var(--font-mono); color: #93c5fd;">{{NOW_ISO}}</code>, <code style="font-family: var(--font-mono); color: #93c5fd;">{{UUID}}</code>, <code style="font-family: var(--font-mono); color: #93c5fd;">{{RANDOM_INT:1:254}}</code>.</span>
          </div>

          <div class="sender-row-3">
            <div class="form-group">
              <label for="sndCount" id="sndCountLabel">Gửi bao nhiêu log</label>
              <input id="sndCount" class="form-control" type="number" min="0" value="1" oninput="schedulePreview()">
              <span class="field-help">0 = không giới hạn</span>
            </div>
            <div class="form-group">
              <label for="sndRate" id="sndRateLabel">Tốc độ (log/giây)</label>
              <input id="sndRate" class="form-control" type="number" min="0.1" max="5000" step="0.1" value="10" oninput="schedulePreview()">
            </div>
            <div class="form-group">
              <label for="sndDuration">Tự dừng sau (giây)</label>
              <input id="sndDuration" class="form-control" type="number" min="0" value="0" oninput="schedulePreview()">
              <span class="field-help">0 = không giới hạn</span>
            </div>
          </div>

          <div class="sender-actions">
            <button class="btn btn-primary" onclick="startSender()">▶ Gửi</button>
            <button class="btn" onclick="startSender(1)">Gửi thử 1 log</button>
          </div>
          <div id="senderMsg" class="sender-msg"></div>
        </div>

        <div class="sender-side">
          <!-- Xem trước -->
          <div class="sender-panel">
            <div class="pv-title"><span>Xem trước</span></div>
            <div id="pvSummary" class="pv-summary" style="color: var(--text-dim);">Điền IP và cổng để xem trước.</div>

            <div id="pvBashWrap" style="display: flex; flex-direction: column; gap: 0.6rem;">
              <div class="pv-title"><span id="pvBashTitle">Lệnh bash tương đương</span><button class="btn copy-btn" onclick="copySenderText('pvCommand')">Sao chép</button></div>
              <div id="pvCommand" class="pv-code">-</div>
            </div>

            <div id="pvPythonWrap" style="display: none; flex-direction: column; gap: 0.6rem;">
              <div class="pv-title"><span id="pvPythonTitle">Code Python tương đương (thư viện logging)</span><button class="btn copy-btn" onclick="copySenderText('pvPython')">Sao chép</button></div>
              <div id="pvPython" class="pv-code" style="max-height: 360px;">-</div>
            </div>

            <div id="pvLoopWrap" style="display: none; flex-direction: column; gap: 0.6rem;">
              <div class="pv-title"><span>Lệnh lặp (theo số lượng / tốc độ)</span><button class="btn copy-btn" onclick="copySenderText('pvLoop')">Sao chép</button></div>
              <div id="pvLoop" class="pv-code">-</div>
            </div>

            <div id="pvShipperWrap" style="display: none; flex-direction: column; gap: 0.6rem;">
              <div class="pv-title"><span>Cấu hình input shipper tương ứng (cym.yml)</span><button class="btn copy-btn" onclick="copySenderText('pvShipper')">Sao chép</button></div>
              <div id="pvShipper" class="pv-code">-</div>
            </div>

            <div id="pvEnvWrap" style="display: none; flex-direction: column; gap: 0.6rem;">
              <div class="pv-title"><span>Biến môi trường cho shipper (export trước khi chạy)</span><button class="btn copy-btn" onclick="copySenderText('pvEnv')">Sao chép</button></div>
              <div id="pvEnv" class="pv-code" style="max-height: 220px;">-</div>
            </div>

            <div class="pv-title"><span id="pvPacketsTitle">Nội dung gói tin thực tế</span></div>
            <div id="pvPackets" class="pv-code">-</div>
            <ul id="pvNotes" class="pv-notes"></ul>
          </div>

          <!-- Danh sách lượt gửi -->
          <div class="sender-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
              <h3>Các lượt gửi</h3>
              <button class="btn btn-danger" onclick="stopAllSenders()">⏹ Dừng tất cả</button>
            </div>
            <div class="table-container" style="box-shadow: none;">
              <table style="width: 100%;">
                <thead>
                  <tr>
                    <th>Trạng thái</th>
                    <th>Gửi tới</th>
                    <th>Đã gửi</th>
                    <th>Lỗi</th>
                    <th>Tốc độ</th>
                    <th style="text-align: right;"></th>
                  </tr>
                </thead>
                <tbody id="senderJobsBody">
                  <tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Chưa có lượt gửi nào</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section id="tab-pubsub" class="tab-content">
      <div style="margin-bottom: 1.25rem;">
        <h2 style="font-size: 1.35rem; font-weight: 700; margin-bottom: 0.35rem;">☁️ GCP Pub/Sub</h2>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Pub/Sub giả lập (fake server chính chủ <code style="font-family: var(--font-mono); color: #93c5fd;">pstest</code> của Google) chạy kèm mock. Input <code style="font-family: var(--font-mono); color: #93c5fd;">gcp_pubsub</code> của shipper kết nối gRPC tới đây nhờ biến môi trường <code style="font-family: var(--font-mono); color: #93c5fd;">PUBSUB_EMULATOR_HOST</code>. Topic / subscription / tốc độ sinh message cấu hình ở <code style="font-family: var(--font-mono); color: #93c5fd;">streams/gcp_pubsub.json</code>.</p>
      </div>
      <div class="sender-layout">
        <div class="sender-panel">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem;">
            <h3>Trạng thái</h3>
            <button class="btn" onclick="fetchPubsub()">↻ Làm mới</button>
          </div>
          <div id="psStatus" class="pv-summary">Đang tải...</div>
          <div class="table-container" style="box-shadow: none;">
            <table style="width: 100%;">
              <thead><tr><th>Topic</th><th>Subscription</th><th>Đã publish</th><th>Tốc độ</th><th style="text-align: right;"></th></tr></thead>
              <tbody id="psTopics"><tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">-</td></tr></tbody>
            </table>
          </div>

          <h3 style="margin-top: 0.5rem;">Đẩy message</h3>
          <div class="sender-row">
            <div class="form-group">
              <label for="psTopic">Topic</label>
              <select id="psTopic" class="form-control"></select>
            </div>
            <div class="form-group">
              <label for="psCount">Số message (sinh từ template)</label>
              <input id="psCount" class="form-control" type="number" min="1" max="100000" value="10">
            </div>
          </div>
          <div class="form-group">
            <label for="psMessages">Hoặc nội dung tự nhập (mỗi dòng 1 message)</label>
            <textarea id="psMessages" class="form-control" style="min-height: 90px; font-family: var(--font-mono); font-size: 0.78rem;" placeholder='{"user": "hoangnx", "action": "login", "time": "{{EVENT_TIME_ISO}}"}'></textarea>
            <span class="field-help">Để trống = sinh "Số message" từ template của topic. Có nội dung = gửi đúng từng dòng (hỗ trợ {{SEQ}}, {{UUID}}, {{EVENT_TIME_ISO}}, {{RANDOM_INT:a:b}}, {{CHOICE:a|b}}). Shipper đọc nội dung vào trường log_raw.</span>
          </div>
          <div class="sender-actions">
            <button class="btn btn-primary" onclick="publishPubsub()">📨 Publish</button>
          </div>
          <div id="psMsg" class="sender-msg"></div>
        </div>

        <div class="sender-side">
          <div class="sender-panel">
            <div class="form-group">
              <label for="psHost">IP máy chạy mock (shipper tới được)</label>
              <input id="psHost" class="form-control" oninput="fetchPubsubConfig()">
              <span class="field-help">Cổng gRPC phải được mở ra ngoài (docker-compose: "8085:8085").</span>
            </div>
            <div class="pv-title"><span>Biến môi trường cho shipper</span><button class="btn copy-btn" onclick="copySenderText('psEnv')">Sao chép</button></div>
            <div id="psEnv" class="pv-code">-</div>
            <div class="pv-title"><span>Cấu hình input (cym.yml)</span><button class="btn copy-btn" onclick="copySenderText('psYml')">Sao chép</button></div>
            <div id="psYml" class="pv-code" style="max-height: 320px;">-</div>
            <ul class="pv-notes">
              <li>PUBSUB_EMULATOR_HOST áp dụng cho cả tiến trình shipper: mọi input gcp_pubsub trên node đó đều vào mock.</li>
              <li>credentials_base64 bắt buộc nhưng emulator không kiểm tra (đây là service account giả).</li>
              <li>Điều kiện nhận diện log source gợi ý: provider equal gcp_audit (shipper gắn provider = log_type).</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  </main>

  <!-- MODAL: REQUEST DETAILS INSPECTOR -->
  <div id="inspectorModal" class="modal-overlay">
    <div class="modal-box">
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <span id="modalMethodBadge" class="badge">GET</span>
          <span id="modalPathTitle" class="modal-title">/path</span>
        </div>
        <button class="btn" onclick="closeInspectorModal()">✕ Đóng</button>
      </div>
      <div class="modal-body">
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem;">
          <div><label style="color: var(--text-dim); font-size: 0.75rem;">Host</label><div id="modalHost" style="font-family: var(--font-mono); font-size: 0.85rem;"></div></div>
          <div><label style="color: var(--text-dim); font-size: 0.75rem;">Status Code</label><div id="modalStatus"></div></div>
          <div><label style="color: var(--text-dim); font-size: 0.75rem;">Xử Lý Bởi</label><div id="modalRule" style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--cyan);"></div></div>
        </div>

        <div>
          <label style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.3rem; display: block;">Request Headers</label>
          <div id="modalReqHeaders" class="code-block"></div>
        </div>

        <div id="modalParamsGroup" style="display: none; margin-top: 1rem;">
          <label style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.3rem; display: block;">Query Parameters</label>
          <table class="params-table" id="modalParamsTable"></table>
        </div>

        <div id="modalReqBodyGroup">
          <label style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.3rem; display: block;">Request Body</label>
          <div id="modalReqBody" class="code-block"></div>
        </div>

        <div>
          <label style="color: var(--text-dim); font-size: 0.75rem; margin-bottom: 0.3rem; display: block;">Response Body</label>
          <div id="modalRespBody" class="code-block"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- MODAL: VIEW & EDIT MOCK RULE -->
  <div id="ruleModal" class="modal-overlay">
    <div class="modal-box modal-box-large">
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <span style="font-size: 1.3rem;">🛠️</span>
          <div>
            <span id="modalRuleTitle" class="modal-title">Chi Tiết & Chỉnh Sửa Mock Rule</span>
            <div id="modalRuleSourceBadge" style="font-size: 0.75rem; color: var(--cyan); font-family: var(--font-mono); margin-top: 0.2rem;">
              📁 File nguồn: rules/01_rest_api.json
            </div>
          </div>
        </div>
        <button class="btn" onclick="closeRuleModal()">✕ Đóng</button>
      </div>
      <div class="modal-body" style="gap: 1.25rem;">
        <input type="hidden" id="editRuleId">
        <input type="hidden" id="editRuleSourceFile">

        <!-- Section 1: Thông tin chung -->
        <div class="form-section">
          <div class="form-section-title">📌 1. Thông Tin Chung</div>
          <div style="display: grid; grid-template-columns: 2fr 1.2fr 1fr auto; gap: 0.75rem; align-items: flex-end;">
            <div class="form-group">
              <label>Tên Rule:</label>
              <input type="text" id="ruleNameInput" class="form-control" placeholder="Tên mô tả rule">
            </div>
            <div class="form-group">
              <label>Category (Nguồn Cloud):</label>
              <select id="ruleCategoryInput" class="form-control">
                <option value="rest_api">Generic REST API</option>
                <option value="azure">Azure Poller</option>
                <option value="defender">Microsoft Defender</option>
                <option value="m365">Microsoft 365</option>
                <option value="cloudwatch">AWS CloudWatch</option>
                <option value="aws_s3sqs">AWS S3-SQS</option>
                <option value="custom">Custom Overrides</option>
                <option value="generic">Khác (Generic)</option>
              </select>
            </div>
            <div class="form-group">
              <label>Phạm Vi Áp Dụng:</label>
              <select id="ruleModeInput" class="form-control">
                <option value="all">⚡ Cả 2 (All)</option>
                <option value="direct">🌐 Direct HTTP</option>
                <option value="proxy">🔒 HTTPS Proxy</option>
              </select>
            </div>
            <div class="form-group" style="padding-bottom: 0.5rem;">
              <label style="display: flex; align-items: center; gap: 0.4rem; cursor: pointer;">
                <input type="checkbox" id="ruleEnabledInput" checked>
                <span style="font-weight: 600; color: var(--success);">Kích hoạt</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Section 2: Khớp Đầu Vào -->
        <div class="form-section">
          <div class="form-section-title">🎯 2. Điều Kiện Khớp Đầu Vào (Match Criteria)</div>
          <div style="display: grid; grid-template-columns: 100px 1.5fr 140px; gap: 0.75rem;">
            <div class="form-group">
              <label>Method:</label>
              <select id="ruleMethodInput" class="form-control">
                <option value="*">* (All)</option>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="DELETE">DELETE</option>
                <option value="HEAD">HEAD</option>
              </select>
            </div>
            <div class="form-group">
              <label>Path URL:</label>
              <input type="text" id="rulePathInput" class="form-control" placeholder="Ví dụ: /mock/rest_api/logs hoặc /subscriptions/content">
            </div>
            <div class="form-group">
              <label>Kiểu Khớp Path:</label>
              <select id="rulePathMatchType" class="form-control">
                <option value="prefix">Prefix (Bắt đầu)</option>
                <option value="exact">Exact (Chính xác)</option>
                <option value="contains">Contains (Chứa)</option>
                <option value="glob">Glob (*.log)</option>
                <option value="regex">Regex</option>
              </select>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label>Host / Domain Filter (cho Proxy hoặc Direct):</label>
              <input type="text" id="ruleHostInput" class="form-control" placeholder="*.amazonaws.com, manage.office.com... (bỏ trống nếu khớp tất cả)">
            </div>
            <div class="form-group">
              <label>Body Chứa (Body Contains):</label>
              <input type="text" id="ruleBodyContainsInput" class="form-control" placeholder="Ví dụ: Action=ReceiveMessage">
            </div>
          </div>

          <div class="form-group">
            <label>Request Headers Bắt Buộc (JSON Object, ví dụ: {"X-Amz-Target": "Logs_20140328"}):</label>
            <input type="text" id="ruleHeadersInput" class="form-control" placeholder='{"X-Amz-Target": "Logs_20140328"}' style="font-family: var(--font-mono);">
          </div>
        </div>

        <!-- Section 3: Phản Hồi Đầu Ra -->
        <div class="form-section">
          <div class="form-section-title">📤 3. Phản Hồi Đầu Ra (Response Definition)</div>
          <div style="display: grid; grid-template-columns: 120px 120px 140px 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label>HTTP Status:</label>
              <input type="number" id="ruleStatusInput" class="form-control" value="200">
            </div>
            <div class="form-group">
              <label>Delay (ms):</label>
              <input type="number" id="ruleDelayInput" class="form-control" value="0">
            </div>
            <div class="form-group">
              <label>Định Dạng Body:</label>
              <select id="ruleBodyTypeInput" class="form-control" onchange="toggleBodyTypeFields()">
                <option value="json">JSON</option>
                <option value="fixture">📂 File Fixture</option>
                <option value="xml">XML (SQS/S3)</option>
                <option value="text">Plain Text</option>
              </select>
            </div>
            <div class="form-group" id="fixtureInputGroup" style="display: none;">
              <label>Đường Dẫn File Fixture (trong fixtures/):</label>
              <input type="text" id="ruleFixtureInput" class="form-control" placeholder="rest_api/default_logs.json" style="font-family: var(--font-mono);">
            </div>
          </div>

          <div class="form-group">
            <label>Response Headers (JSON Object):</label>
            <input type="text" id="ruleRespHeadersInput" class="form-control" placeholder='{"Content-Type": "application/json"}' style="font-family: var(--font-mono);">
          </div>

          <div class="form-group" id="bodyInputGroup">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
              <label style="margin-bottom: 0;">Nội Dung Response Body (Hỗ trợ biến động: {{NOW_ISO}}, {{TIMESTAMP}}, {{UUID}}, {{NOW_MS}}):</label>
              <button type="button" class="btn" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;" onclick="formatJsonBody()">✨ Làm đẹp JSON</button>
            </div>
            <textarea id="ruleBodyInput" class="form-control" style="min-height: 150px;" placeholder='{\n  "status": "ok",\n  "time": "{{NOW_ISO}}"\n}'></textarea>
          </div>
        </div>
      </div>
      <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center;">
        <span id="modalSaveHint" style="font-size: 0.8rem; color: var(--text-dim);">Thay đổi sẽ được lưu trực tiếp vào file JSON cấu hình.</span>
        <div style="display: flex; gap: 0.6rem;">
          <button class="btn" onclick="closeRuleModal()">Hủy</button>
          <button class="btn btn-primary" onclick="submitRuleModal()">💾 Lưu Thay Đổi & Nạp Ngay</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentLogs = [];
    let currentScenarios = [];
    let currentRules = [];
    let modalMode = 'create'; // 'create' or 'edit'

    function setTab(tabId, btnElement) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

      const btn = btnElement || document.getElementById('tabBtn-' + tabId) || document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
      if (btn) btn.classList.add('active');

      const targetEl = document.getElementById('tab-' + tabId);
      if (targetEl) targetEl.classList.add('active');

      if (tabId === 'scenarios') fetchScenarios();
      if (tabId === 'rules') fetchRules();
      if (tabId === 'sender') { loadSenderDefaults(); fetchSenderJobs(); }
      if (tabId === 'pubsub') { fetchPubsub(); fetchPubsubConfig(); }
    }

    async function fetchStatus() {
      try {
        const res = await fetch('/mock/admin/api/status');
        const data = await res.json();
        document.getElementById('statTotalReq').innerText = data.total_logged_requests;
        document.getElementById('statActiveScenario').innerText = data.active_scenario;
        document.getElementById('statActiveRules').innerText = data.active_rules_count;
        document.getElementById('statUptime').innerText = data.uptime_seconds + 's';
        document.getElementById('reqCount').innerText = data.total_logged_requests;
        document.getElementById('rulesCount').innerText = data.active_rules_count;
        const pill = document.getElementById('rulesActivePill');
        if (pill) pill.innerText = data.active_rules_count + ' Rules';
      } catch (e) {
        console.error('Failed to fetch status', e);
      }
    }

    async function fetchLogs() {
      try {
        const search = document.getElementById('logSearchInput').value;
        const status = document.getElementById('statusFilter').value;
        const url = `/mock/admin/api/logs?limit=100&search=${encodeURIComponent(search)}&status=${status}`;
        const res = await fetch(url);
        const data = await res.json();
        currentLogs = data.logs || [];
        renderLogsTable();
      } catch (e) {
        console.error('Failed to fetch logs', e);
      }
    }

    let selectedLogId = null;
    let currentSubTab = 'req';

    function setSubTab(tab) {
      currentSubTab = tab;
      document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
      const activeBtn = document.getElementById('subtabBtn-' + tab);
      if (activeBtn) activeBtn.classList.add('active');

      const reqPanel = document.getElementById('subtab-req');
      const respPanel = document.getElementById('subtab-resp');
      const metaPanel = document.getElementById('subtab-meta');
      if (reqPanel) reqPanel.style.display = (tab === 'req') ? 'flex' : 'none';
      if (respPanel) respPanel.style.display = (tab === 'resp') ? 'flex' : 'none';
      if (metaPanel) metaPanel.style.display = (tab === 'meta') ? 'flex' : 'none';
    }

    function renderLogsTable() {
      const tbody = document.getElementById('logsTableBody');
      if (!tbody) return;
      if (currentLogs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2.5rem;">Chưa có request nào từ Shipper. Hãy gửi request hoặc khởi động Shipper!</td></tr>';
        const card = document.getElementById('sideInspectorCard');
        if (card) card.style.opacity = '0.4';
        return;
      }
      const card = document.getElementById('sideInspectorCard');
      if (card) card.style.opacity = '1';

      if (!selectedLogId || !currentLogs.find(l => l.id === selectedLogId)) {
        selectedLogId = currentLogs[0].id;
      }

      let html = '';
      currentLogs.forEach(log => {
        const isSelected = (log.id === selectedLogId);
        const methodClass = 'badge-method-' + log.method.toLowerCase();
        let statusClass = 'badge-status-2xx';
        if (log.status >= 400 && log.status < 500) statusClass = 'badge-status-4xx';
        if (log.status >= 500) statusClass = 'badge-status-5xx';

        const timeOnly = log.timestamp.split(' ')[1] || log.timestamp;
        html += `<tr class="${isSelected ? 'selected-log-row' : ''}" onclick="selectLog(${log.id})">
          <td style="font-family: var(--font-mono); color: var(--text-dim); font-size: 0.75rem;">#${log.id}</td>
          <td style="font-family: var(--font-mono); font-size: 0.78rem;">${timeOnly}</td>
          <td><span class="badge ${methodClass}">${log.method}</span></td>
          <td>
            <div style="font-weight: 600; word-break: break-all; font-size: 0.82rem; color: #f1f5f9;">${log.path}</div>
            ${log.host ? `<div style="font-size: 0.72rem; color: var(--text-dim);">${log.host}</div>` : ''}
            <div style="font-size: 0.7rem; color: var(--cyan); margin-top: 0.25rem; font-family: var(--font-mono); line-height: 1.2;">
              ${log.params && Object.keys(log.params).length > 0 ? 
                Object.entries(log.params).map(([k,v]) => `<span style="background: rgba(34, 211, 238, 0.1); padding: 0.1rem 0.3rem; border-radius: 3px; border: 1px solid rgba(34,211,238,0.2); margin-right: 0.25rem; display: inline-block; margin-bottom: 0.1rem;"><b>${k}</b>: ${Array.isArray(v) ? v.join(',') : v}</span>`).join('') 
                : '<span style="color: var(--text-dim); font-style: italic;">(Không có Query Params)</span>'}
            </div>
          </td>
          <td><span class="badge ${statusClass}">${log.status}</span></td>
          <td style="text-align: center;">
            <button class="btn btn-sm" onclick="event.stopPropagation(); openInspectorModal(${log.id})" style="padding: 0.2rem 0.5rem; font-size: 0.72rem;">👁️ Xem</button>
          </td>
        </tr>`;
      });
      tbody.innerHTML = html;

      const activeLog = currentLogs.find(l => l.id === selectedLogId);
      if (activeLog) {
        renderSideInspector(activeLog);
      }
    }

    function selectLog(logId) {
      selectedLogId = logId;
      document.querySelectorAll('#logsTableBody tr').forEach(r => r.classList.remove('selected-log-row'));
      renderLogsTable();
    }

    function renderSideInspector(log) {
      if (!log) return;
      const mBadge = document.getElementById('sideMethodBadge');
      if (mBadge) {
        mBadge.innerText = log.method;
        mBadge.className = 'badge badge-method-' + log.method.toLowerCase();
      }
      const pTitle = document.getElementById('sidePathTitle');
      if (pTitle) {
        pTitle.innerText = log.path;
        pTitle.title = log.path;
      }

      let statusClass = 'badge-status-2xx';
      if (log.status >= 400 && log.status < 500) statusClass = 'badge-status-4xx';
      if (log.status >= 500) statusClass = 'badge-status-5xx';
      const sBadge = document.getElementById('sideStatusBadge');
      if (sBadge) {
        sBadge.className = 'badge ' + statusClass;
        sBadge.innerText = log.status;
      }

      const cIp = document.getElementById('sideClientIp');
      if (cIp) cIp.innerText = 'Client IP: ' + (log.client_ip || '127.0.0.1');

      const proto = (log.host && log.host.includes(':443')) ? 'https://' : 'http://';
      const fUrl = document.getElementById('sideFullUrl');
      if (fUrl) fUrl.innerText = `${proto}${log.host || 'localhost'}${log.path}`;

      // Query params
      const paramsGroup = document.getElementById('sideParamsGroup');
      const paramsTable = document.getElementById('sideParamsTable');
      if (paramsGroup && paramsTable) {
        if (log.params && Object.keys(log.params).length > 0) {
          let phtml = '';
          for (const [k, v] of Object.entries(log.params)) {
            const valStr = Array.isArray(v) ? v.join(', ') : v;
            phtml += `<tr><td class="param-key">${k}</td><td class="param-val">${valStr}</td></tr>`;
          }
          paramsTable.innerHTML = phtml;
          paramsGroup.style.display = 'block';
        } else {
          paramsGroup.style.display = 'none';
        }
      }

      // Request Body
      let reqBodyFormatted = log.request_body || '(Trống)';
      try {
        if (log.request_body && (log.request_body.startsWith('{') || log.request_body.startsWith('['))) {
          reqBodyFormatted = JSON.stringify(JSON.parse(log.request_body), null, 2);
        }
      } catch (e) {}
      const sReqBody = document.getElementById('sideReqBody');
      if (sReqBody) sReqBody.innerText = reqBodyFormatted;

      // Request Headers
      const sReqHeaders = document.getElementById('sideReqHeaders');
      if (sReqHeaders) sReqHeaders.innerText = JSON.stringify(log.request_headers, null, 2);

      // Response Body
      let respBodyFormatted = log.response_body || '(Trống)';
      try {
        if (log.response_body && (log.response_body.startsWith('{') || log.response_body.startsWith('['))) {
          respBodyFormatted = JSON.stringify(JSON.parse(log.response_body), null, 2);
        }
      } catch (e) {}
      const sRespBody = document.getElementById('sideRespBody');
      if (sRespBody) sRespBody.innerText = respBodyFormatted;

      // Response Headers
      const sRespHeaders = document.getElementById('sideRespHeaders');
      if (sRespHeaders) sRespHeaders.innerText = JSON.stringify(log.response_headers, null, 2);

      // Meta
      const sRule = document.getElementById('sideMatchedRule');
      if (sRule) sRule.innerText = log.matched_rule || '-';
      const sDur = document.getElementById('sideDuration');
      if (sDur) sDur.innerText = log.duration_ms + 'ms';
      const sHost = document.getElementById('sideHost');
      if (sHost) sHost.innerText = log.host || 'localhost';
      const sTime = document.getElementById('sideTimestamp');
      if (sTime) sTime.innerText = log.timestamp;
    }

    function copyToClipboard(text, btn) {
      navigator.clipboard.writeText(text).then(() => {
        if (!btn) return;
        const orig = btn.innerText;
        btn.innerText = '✅ Đã Copy!';
        setTimeout(() => { btn.innerText = orig; }, 1800);
      });
    }

    function copyReqBody() {
      const log = currentLogs.find(l => l.id === selectedLogId);
      if (log && log.request_body) copyToClipboard(log.request_body, event.target);
    }

    function copyReqHeaders() {
      const log = currentLogs.find(l => l.id === selectedLogId);
      if (log && log.request_headers) copyToClipboard(JSON.stringify(log.request_headers, null, 2), event.target);
    }

    function copyRespBody() {
      const log = currentLogs.find(l => l.id === selectedLogId);
      if (log && log.response_body) copyToClipboard(log.response_body, event.target);
    }

    function copyCurrentCurl() {
      const log = currentLogs.find(l => l.id === selectedLogId);
      if (!log) return;
      const proto = (log.host && log.host.includes(':443')) ? 'https://' : 'http://';
      let cmd = `curl -X ${log.method} "${proto}${log.host || 'localhost'}${log.path}"`;
      if (log.request_headers) {
        for (const [k, v] of Object.entries(log.request_headers)) {
          if (!['host', 'content-length'].includes(k.toLowerCase())) {
            cmd += ` \\\n  -H "${k}: ${v}"`;
          }
        }
      }
      if (log.request_body && log.request_body.trim() !== '') {
        cmd += ` \\\n  -d '${log.request_body.replace(/'/g, "'\\''")}'`;
      }
      copyToClipboard(cmd, event.target);
    }

    function openCurrentInModal() {
      if (selectedLogId) openInspectorModal(selectedLogId);
    }

    function filterLogs() {
      fetchLogs();
    }

    async function clearLogs() {
      if (!confirm('Bạn có chắc chắn muốn xóa toàn bộ request logs hiện tại?')) return;
      await fetch('/mock/admin/api/logs/clear', { method: 'POST' });
      selectedLogId = null;
      fetchLogs();
      fetchStatus();
    }

    function openInspectorModal(logId) {
      const log = currentLogs.find(l => l.id === logId);
      if (!log) return;

      document.getElementById('modalMethodBadge').innerText = log.method;
      document.getElementById('modalMethodBadge').className = 'badge badge-method-' + log.method.toLowerCase();
      document.getElementById('modalPathTitle').innerText = log.path;
      document.getElementById('modalHost').innerText = log.host || 'localhost';
      document.getElementById('modalStatus').innerHTML = `<span class="badge badge-status-${log.status >= 400 ? (log.status >= 500 ? '5xx' : '4xx') : '2xx'}">${log.status}</span>`;
      document.getElementById('modalRule').innerText = log.matched_rule;

      document.getElementById('modalReqHeaders').innerText = JSON.stringify(log.request_headers, null, 2);
      
      const modalParamsGroup = document.getElementById('modalParamsGroup');
      const modalParamsTable = document.getElementById('modalParamsTable');
      if (modalParamsGroup && modalParamsTable) {
        modalParamsGroup.style.display = 'block';
        if (log.params && Object.keys(log.params).length > 0) {
          let phtml = '';
          for (const [k, v] of Object.entries(log.params)) {
            const valStr = Array.isArray(v) ? v.join(', ') : v;
            phtml += `<tr><td class="param-key">${k}</td><td class="param-val">${valStr}</td></tr>`;
          }
          modalParamsTable.innerHTML = phtml;
        } else {
          modalParamsTable.innerHTML = '<tr><td colspan="2" style="color: var(--text-dim); font-style: italic; padding: 0.5rem 0;">(Trống)</td></tr>';
        }
      }

      document.getElementById('modalReqBody').innerText = log.request_body || '(Trống)';
      document.getElementById('modalRespBody').innerText = log.response_body || '(Trống)';

      document.getElementById('inspectorModal').classList.add('open');
    }

    function closeInspectorModal() {
      document.getElementById('inspectorModal').classList.remove('open');
    }

    async function fetchScenarios(alertReload = false) {
      try {
        if (alertReload) {
          await fetch('/mock/admin/api/scenarios/reload', { method: 'POST' });
        }
        const res = await fetch('/mock/admin/api/scenarios');
        const data = await res.json();
        currentScenarios = data.scenarios || [];

        // Update Header select
        const sel = document.getElementById('quickScenarioSelect');
        sel.innerHTML = '';
        currentScenarios.forEach(sc => {
          const opt = document.createElement('option');
          opt.value = sc.name;
          opt.innerText = sc.name + (sc.is_active ? ' ✓' : '');
          if (sc.is_active) opt.selected = true;
          sel.appendChild(opt);
        });

        // Render Scenarios Cards
        const grid = document.getElementById('scenariosGrid');
        if (grid) {
          let html = '';
          currentScenarios.forEach(sc => {
            const isActive = sc.is_active;
            html += `<div class="scenario-card ${isActive ? 'active-card' : ''}">
              <div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                  <span style="font-weight: 700; font-size: 1.1rem; color: ${isActive ? '#60a5fa' : 'var(--text-main)'};">🎭 ${sc.name}</span>
                  ${isActive ? '<span class="badge" style="background: rgba(59,130,246,0.2); color: #60a5fa;">HOẠT ĐỘNG</span>' : ''}
                </div>
                <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">${sc.description || 'Kịch bản giả lập'}</p>
                <div style="margin-top: 0.75rem; font-size: 0.75rem; color: var(--text-dim); font-family: var(--font-mono);">
                  Số rules định nghĩa: ${sc.rules_count}
                </div>
              </div>
              <div>
                ${isActive
                  ? '<button class="btn" style="width: 100%; justify-content: center;" disabled>Đang Kích Hoạt</button>'
                  : `<button class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="switchScenario('${sc.name}')">Kích Hoạt Kịch Bản Này</button>`
                }
              </div>
            </div>`;
          });
          grid.innerHTML = html;
        }

        if (alertReload) alert('Đã nạp lại các file kịch bản từ thư mục scenarios/ thành công!');
      } catch (e) {
        console.error('Failed to fetch scenarios', e);
      }
    }

    async function switchScenario(name) {
      try {
        const res = await fetch('/mock/admin/api/scenarios/switch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario: name })
        });
        const data = await res.json();
        if (data.success) {
          fetchStatus();
          fetchScenarios();
          fetchRules();
        } else {
          alert('Lỗi: ' + data.error);
        }
      } catch (e) {
        console.error(e);
      }
    }

    // ==========================================
    // RULES MANAGEMENT & EDITING
    // ==========================================
    async function fetchRules() {
      try {
        const res = await fetch('/mock/admin/api/rules');
        const data = await res.json();
        currentRules = data.rules || [];
        filterRules();
      } catch (e) {
        console.error('Failed to fetch rules', e);
      }
    }

    function filterRules() {
      const search = (document.getElementById('ruleSearchInput')?.value || '').toLowerCase().trim();
      const cat = document.getElementById('ruleCategoryFilter')?.value || '';
      const mode = document.getElementById('ruleModeFilter')?.value || '';
      const statusFilter = document.getElementById('ruleStatusFilter')?.value || '';

      const filtered = currentRules.filter(r => {
        if (cat && r.category !== cat && !(cat === 'custom' && r.source === 'dynamic_override')) return false;
        if (mode && (r.mode || 'all') !== mode) return false;
        if (statusFilter && String(r.response?.status || 200) !== statusFilter) return false;

        if (search) {
          const matchStr = [
            r.name,
            r.id,
            r.match?.path || '',
            r.match?.host || '',
            r.match?.method || '',
            r.source_file || '',
            r.category || ''
          ].join(' ').toLowerCase();
          if (!matchStr.includes(search)) return false;
        }
        return true;
      });

      renderRulesTable(filtered);
    }

    function renderRulesTable(rulesToRender = currentRules) {
      const tbody = document.getElementById('rulesTableBody');
      if (!tbody) return;
      if (rulesToRender.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 2rem;">Không tìm thấy rule nào khớp với bộ lọc.</td></tr>';
        return;
      }

      let html = '';
      rulesToRender.forEach(r => {
        const isDynamic = r.source === 'dynamic_override';
        const method = r.match?.method || '*';
        const path = r.match?.path || '*';
        const status = r.response?.status || 200;
        const delay = r.response?.delay_ms || 0;
        const bodyType = r.response?.body_type || (r.response?.fixture ? 'fixture' : 'json');

        const mode = r.mode || 'all';
        let modeBadge = '<span class="badge" style="background: rgba(16,185,129,0.1); color: #34d399;">⚡ All</span>';
        if (mode === 'proxy') modeBadge = '<span class="badge" style="background: rgba(139,92,246,0.15); color: #c084fc;">🔒 Proxy</span>';
        if (mode === 'direct') modeBadge = '<span class="badge" style="background: rgba(59,130,246,0.15); color: #60a5fa;">🌐 Direct</span>';

        const cat = r.category || 'generic';
        const catBadge = `<span class="badge badge-cat-${cat}">${cat.toUpperCase()}</span>`;

        let respDesc = '';
        if (bodyType === 'fixture') {
          respDesc = `<div style="font-size: 0.72rem; color: #38bdf8; word-break: break-all;">📁 ${r.response.fixture || ''}</div>`;
        } else {
          respDesc = `<div style="font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;">Type: ${bodyType}</div>`;
        }
        if (delay > 0) {
          respDesc += `<div style="font-size: 0.7rem; color: var(--warning);">⏱️ Delay ${delay}ms</div>`;
        }

        const sourceLabel = r.source_file ? `rules/${r.source_file}` : (r.source || 'rules');

        html += `<tr style="${r.enabled ? '' : 'opacity: 0.55;'}">
          <td style="text-align: center;" onclick="event.stopPropagation()">
            <input type="checkbox" ${r.enabled ? 'checked' : ''} onchange="toggleRule('${r.id}', this.checked)">
          </td>
          <td onclick="openEditRuleModal('${r.id}')" style="cursor: pointer;">
            <div style="font-weight: 600; color: var(--text-main); font-size: 0.9rem;">
              ${r.name}
            </div>
            <div style="font-size: 0.72rem; color: var(--text-dim); font-family: var(--font-mono); margin-top: 0.2rem;">
              <span>${r.id}</span> &bull; <span style="color: var(--cyan);">${sourceLabel}</span>
            </div>
          </td>
          <td>${catBadge}</td>
          <td>${modeBadge}</td>
          <td><span class="badge badge-method-${method.toLowerCase()}">${method}</span></td>
          <td onclick="openEditRuleModal('${r.id}')" style="cursor: pointer; font-family: var(--font-mono); font-size: 0.8rem;">
            ${r.match?.host ? `<div style="color: var(--cyan); font-size: 0.75rem;">🌐 Host: ${r.match.host}</div>` : ''}
            <div style="color: #93c5fd; font-weight: 500;">${path}</div>
            ${r.match?.body_contains ? `<div style="color: var(--text-dim); font-size: 0.72rem;">body: ${r.match.body_contains}</div>` : ''}
            ${r.match?.headers ? `<div style="color: var(--purple); font-size: 0.72rem;">header: ${Object.keys(r.match.headers).join(', ')}</div>` : ''}
          </td>
          <td>
            <span class="badge badge-status-${status >= 400 ? (status >= 500 ? '5xx' : '4xx') : '2xx'}">${status}</span>
            ${respDesc}
          </td>
          <td style="font-family: var(--font-mono); text-align: center;">${r.hit_count}</td>
          <td style="text-align: right;" onclick="event.stopPropagation()">
            <div style="display: flex; gap: 0.4rem; justify-content: flex-end;">
              <button class="btn" style="padding: 0.3rem 0.6rem; font-size: 0.75rem;" onclick="openEditRuleModal('${r.id}')">✏️ Sửa</button>
              ${isDynamic ? `<button class="btn btn-danger" style="padding: 0.3rem 0.5rem; font-size: 0.75rem;" onclick="deleteRule('${r.id}')">🗑️</button>` : ''}
            </div>
          </td>
        </tr>`;
      });
      tbody.innerHTML = html;
    }

    async function toggleRule(id, enabled) {
      try {
        await fetch(`/mock/admin/api/rules/${id}/toggle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled })
        });
        const rule = currentRules.find(r => r.id === id);
        if (rule) rule.enabled = enabled;
        filterRules();
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    }

    async function deleteRule(id) {
      if (!confirm(`Xóa dynamic rule '${id}'?`)) return;
      try {
        await fetch(`/mock/admin/api/rules/${id}`, { method: 'DELETE' });
        fetchRules();
        fetchStatus();
      } catch (e) {
        console.error(e);
      }
    }

    function toggleBodyTypeFields() {
      const type = document.getElementById('ruleBodyTypeInput').value;
      const fixtureGroup = document.getElementById('fixtureInputGroup');
      const bodyGroup = document.getElementById('bodyInputGroup');

      if (type === 'fixture') {
        fixtureGroup.style.display = 'flex';
        bodyGroup.style.display = 'none';
      } else {
        fixtureGroup.style.display = 'none';
        bodyGroup.style.display = 'flex';
      }
    }

    function formatJsonBody() {
      const txt = document.getElementById('ruleBodyInput');
      try {
        const obj = JSON.parse(txt.value);
        txt.value = JSON.stringify(obj, null, 2);
      } catch (e) {
        alert('Nội dung không phải là JSON hợp lệ: ' + e.message);
      }
    }

    function openEditRuleModal(ruleId) {
      const rule = currentRules.find(r => r.id === ruleId);
      if (!rule) return;

      modalMode = 'edit';
      document.getElementById('editRuleId').value = rule.id;
      document.getElementById('editRuleSourceFile').value = rule.source_file || '';
      document.getElementById('modalRuleTitle').innerText = '✏️ Chỉnh Sửa Mock Rule: ' + rule.name;
      document.getElementById('modalRuleSourceBadge').innerText = rule.source_file ? `📁 File cấu hình: rules/${rule.source_file}` : `📁 Nguồn: ${rule.source || 'rules'}`;

      document.getElementById('ruleNameInput').value = rule.name || '';
      document.getElementById('ruleCategoryInput').value = rule.category || 'generic';
      document.getElementById('ruleModeInput').value = rule.mode || 'all';
      document.getElementById('ruleEnabledInput').checked = rule.enabled !== false;

      // Match criteria
      document.getElementById('ruleMethodInput').value = rule.match?.method || '*';
      document.getElementById('rulePathInput').value = rule.match?.path || '';
      document.getElementById('rulePathMatchType').value = rule.match?.path_match || 'prefix';
      document.getElementById('ruleHostInput').value = rule.match?.host || '';
      document.getElementById('ruleBodyContainsInput').value = rule.match?.body_contains || '';

      if (rule.match?.headers) {
        document.getElementById('ruleHeadersInput').value = JSON.stringify(rule.match.headers);
      } else {
        document.getElementById('ruleHeadersInput').value = '';
      }

      // Response
      document.getElementById('ruleStatusInput').value = rule.response?.status || 200;
      document.getElementById('ruleDelayInput').value = rule.response?.delay_ms || 0;

      const bodyType = rule.response?.body_type || (rule.response?.fixture ? 'fixture' : 'json');
      document.getElementById('ruleBodyTypeInput').value = bodyType;
      document.getElementById('ruleFixtureInput').value = rule.response?.fixture || '';

      if (rule.response?.headers) {
        document.getElementById('ruleRespHeadersInput').value = JSON.stringify(rule.response.headers);
      } else {
        document.getElementById('ruleRespHeadersInput').value = '{"Content-Type": "application/json"}';
      }

      const bodyContent = rule.response?.body;
      if (typeof bodyContent === 'object' && bodyContent !== null) {
        document.getElementById('ruleBodyInput').value = JSON.stringify(bodyContent, null, 2);
      } else {
        document.getElementById('ruleBodyInput').value = bodyContent || '';
      }

      toggleBodyTypeFields();
      document.getElementById('ruleModal').classList.add('open');
    }

    function openNewRuleModal() {
      modalMode = 'create';
      document.getElementById('editRuleId').value = '';
      document.getElementById('editRuleSourceFile').value = 'custom_overrides.json';
      document.getElementById('modalRuleTitle').innerText = '➕ Tạo Rule Mock Đầu Vào & Đầu Ra Mới';
      document.getElementById('modalRuleSourceBadge').innerText = '📁 File lưu: rules/custom_overrides.json (Độ ưu tiên cao nhất)';

      document.getElementById('ruleNameInput').value = '';
      document.getElementById('ruleCategoryInput').value = 'custom';
      document.getElementById('ruleModeInput').value = 'all';
      document.getElementById('ruleEnabledInput').checked = true;

      document.getElementById('ruleMethodInput').value = 'GET';
      document.getElementById('rulePathInput').value = '';
      document.getElementById('rulePathMatchType').value = 'prefix';
      document.getElementById('ruleHostInput').value = '';
      document.getElementById('ruleBodyContainsInput').value = '';
      document.getElementById('ruleHeadersInput').value = '';

      document.getElementById('ruleStatusInput').value = 200;
      document.getElementById('ruleDelayInput').value = 0;
      document.getElementById('ruleBodyTypeInput').value = 'json';
      document.getElementById('ruleFixtureInput').value = '';
      document.getElementById('ruleRespHeadersInput').value = '{"Content-Type": "application/json"}';
      document.getElementById('ruleBodyInput').value = JSON.stringify({
        status: "success",
        message: "Mock response",
        timestamp: "{{NOW_ISO}}"
      }, null, 2);

      toggleBodyTypeFields();
      document.getElementById('ruleModal').classList.add('open');
    }

    function closeRuleModal() {
      document.getElementById('ruleModal').classList.remove('open');
    }

    async function submitRuleModal() {
      const name = document.getElementById('ruleNameInput').value.trim();
      if (!name) {
        alert('Vui lòng nhập Tên Rule!');
        return;
      }

      const category = document.getElementById('ruleCategoryInput').value;
      const mode = document.getElementById('ruleModeInput').value;
      const enabled = document.getElementById('ruleEnabledInput').checked;

      const method = document.getElementById('ruleMethodInput').value;
      const path = document.getElementById('rulePathInput').value.trim();
      const pathMatch = document.getElementById('rulePathMatchType').value;
      const host = document.getElementById('ruleHostInput').value.trim();
      const bodyContains = document.getElementById('ruleBodyContainsInput').value.trim();
      const headersStr = document.getElementById('ruleHeadersInput').value.trim();

      const status = parseInt(document.getElementById('ruleStatusInput').value) || 200;
      const delay = parseInt(document.getElementById('ruleDelayInput').value) || 0;
      const bodyType = document.getElementById('ruleBodyTypeInput').value;
      const fixture = document.getElementById('ruleFixtureInput').value.trim();
      const respHeadersStr = document.getElementById('ruleRespHeadersInput').value.trim();
      const bodyRaw = document.getElementById('ruleBodyInput').value.trim();

      if (!path && !bodyContains && !host && method === '*') {
        alert('Vui lòng chỉ định Path URL hoặc Host hoặc Body Contains để làm điều kiện khớp!');
        return;
      }

      let parsedHeaders = undefined;
      if (headersStr) {
        try {
          parsedHeaders = JSON.parse(headersStr);
        } catch (e) {
          alert('Request Headers phải là định dạng JSON hợp lệ (ví dụ: {"X-Header": "value"})');
          return;
        }
      }

      let parsedRespHeaders = { "Content-Type": "application/json" };
      if (respHeadersStr) {
        try {
          parsedRespHeaders = JSON.parse(respHeadersStr);
        } catch (e) {
          alert('Response Headers phải là định dạng JSON hợp lệ (ví dụ: {"Content-Type": "application/json"})');
          return;
        }
      }

      let parsedBody = bodyRaw;
      if (bodyType === 'json' && bodyRaw) {
        try {
          parsedBody = JSON.parse(bodyRaw);
        } catch (e) {
          // Keep as string if parsing fails
        }
      }

      const matchObj = {
        method,
        path: path || undefined,
        path_match: path ? pathMatch : undefined,
        host: host || undefined,
        body_contains: bodyContains || undefined,
        headers: parsedHeaders
      };

      const respObj = {
        status,
        delay_ms: delay,
        body_type: bodyType,
        headers: parsedRespHeaders
      };

      if (bodyType === 'fixture') {
        respObj.fixture = fixture;
      } else {
        respObj.body = parsedBody;
      }

      const rulePayload = {
        name,
        category,
        enabled,
        mode,
        match: matchObj,
        response: respObj
      };

      try {
        let res;
        if (modalMode === 'edit') {
          const ruleId = document.getElementById('editRuleId').value;
          rulePayload.id = ruleId;
          res = await fetch(`/mock/admin/api/rules/${ruleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rulePayload)
          });
        } else {
          res = await fetch('/mock/admin/api/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rulePayload)
          });
        }

        const data = await res.json();
        if (data.success) {
          closeRuleModal();
          await fetchRules();
          fetchStatus();
          alert(data.message || 'Lưu rule thành công!');
        } else {
          alert('Lỗi: ' + (data.error || data.message));
        }
      } catch (e) {
        console.error(e);
        alert('Lỗi kết nối tới máy chủ khi lưu rule: ' + e.message);
      }
    }

    async function reloadRulesFromDisk() {
      try {
        const res = await fetch('/mock/admin/api/rules/reload', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          await fetchRules();
          fetchStatus();
          alert(data.message || 'Đã nạp lại toàn bộ rules và scenarios từ ổ đĩa thành công!');
        } else {
          alert('Lỗi nạp rules: ' + data.error);
        }
      } catch (e) {
        console.error(e);
      }
    }


    // ===== Mock Sender =====
    const SENDER_NL = String.fromCharCode(10);
    const SENDER_FORM_KEY = 'mockSenderForm.v5';
    let senderDefaults = null;
    let senderPreviewTimer = null;
    let senderMode = 'syslog';         // syslog | udp | tcp
    const SENDER_MODE_NAMES = { syslog: 'Syslog', udp: 'UDP · logging', tcp: 'TCP · logging', redis: 'Redis', beats: 'Beats · Lumberjack', http: 'HTTP · POST' };

    function senderFormKey(mode) {
      return SENDER_FORM_KEY + (mode === 'syslog' ? '' : '.' + mode);
    }

    function senderTransport() {
      return senderMode === 'syslog' ? document.getElementById('sndTransport').value : senderMode;
    }

    const SENDER_HELP = {
      host: {
        net: 'IP máy đang chạy shipper. Mock chạy trong Docker thì 127.0.0.1 là chính container; dùng IP gateway Docker (vd 172.22.0.1) để tới máy host.',
        redis: 'IP máy chạy Redis mà input redis của shipper đọc. Mock chạy trong Docker thì dùng IP gateway Docker (vd 172.22.0.1) để tới Redis trên máy host.',
        beats: 'IP máy chạy shipper có input beats. Mock chạy trong Docker thì dùng IP gateway Docker (vd 172.22.0.1) để tới máy host.',
        http: 'IP máy chạy shipper có input http. Mock chạy trong Docker thì dùng IP gateway Docker (vd 172.22.0.1) để tới máy host.'
      },
      port: { net: 'Cổng của input syslog / udp / tcp trong cấu hình shipper.', redis: 'Cổng Redis (mặc định 6379).',
              beats: 'Cổng của input beats (mặc định 5044).', http: 'Cổng của input http (port trong cấu hình, mặc định 8080).' },
      msg: {
        syslog: 'Mock gửi đúng từng ký tự bạn nhập, không tự thêm header.',
        logging: 'Nội dung này là %(message)s; dòng gửi đi được tạo theo "Định dạng dòng log" ở trên.',
        redis: 'Mỗi log là một phần tử (value) đẩy vào key, giữ nguyên văn.',
        beats: 'Mỗi dòng là 1 event JSON (giả Filebeat). Dòng không phải JSON được bọc thành {"message": ...}. Event thiếu "message" sẽ bị shipper bỏ.',
        http: 'Mỗi dòng là 1 log JSON; mỗi request gửi một mảng gồm "Số log mỗi request" log. Dòng không phải JSON được bọc thành {"message": ...}.'
      }
    };

    function setSenderMode(mode) {
      if (mode === senderMode) return;
      collectSenderConfig();            // lưu form của tab đang mở
      senderMode = mode;
      document.querySelectorAll('.sender-modes .sub-tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('senderModeBtn-' + mode).classList.add('active');
      try { localStorage.setItem(SENDER_FORM_KEY + '.mode', mode); } catch (e) {}
      clearSenderPreview('Đang tạo xem trước...', false);
      restoreSenderForm();
      updateSenderVisibility();
      schedulePreview();
    }

    function updateSenderVisibility() {
      const redis = senderMode === 'redis';
      const beats = senderMode === 'beats';
      const http = senderMode === 'http';
      const logging = senderMode === 'udp' || senderMode === 'tcp';
      const batched = beats || http;
      const helpKey = (redis || beats || http) ? senderMode : 'net';
      document.getElementById('sndTransportGroup').style.display = senderMode === 'syslog' ? '' : 'none';
      document.getElementById('sndLoggingOpts').style.display = logging ? 'flex' : 'none';
      document.getElementById('sndRedisOpts').style.display = redis ? 'flex' : 'none';
      document.getElementById('sndBeatsOpts').style.display = beats ? 'flex' : 'none';
      document.getElementById('sndHttpOpts').style.display = http ? 'flex' : 'none';
      document.getElementById('sndNewlineGroup').style.display = (redis || batched || senderTransport() === 'tcp') ? 'none' : 'flex';
      document.getElementById('sndHostHelp').innerText = SENDER_HELP.host[helpKey];
      document.getElementById('sndPortHelp').innerText = SENDER_HELP.port[helpKey];
      document.getElementById('sndMsgHelp').innerText = SENDER_HELP.msg[(redis || batched) ? senderMode : (logging ? 'logging' : 'syslog')];
      document.getElementById('pvBashTitle').innerText = redis ? 'Lệnh redis-cli tương đương' : beats ? 'Cấu hình Filebeat tương đương'
        : http ? 'Lệnh curl tương đương' : 'Lệnh bash tương đương';
      document.getElementById('pvPythonTitle').innerText = beats ? 'Code Python tương đương (Lumberjack v2)' : 'Code Python tương đương (thư viện logging)';
      document.getElementById('pvPacketsTitle').innerText = redis ? 'Giá trị đẩy vào Redis' : beats ? 'Event mẫu (JSON)'
        : http ? 'Body JSON của 1 request' : 'Nội dung gói tin thực tế';
      const unit = beats ? 'batch' : http ? 'request' : 'log';
      document.getElementById('sndCountLabel').innerText = 'Gửi bao nhiêu ' + unit;
      document.getElementById('sndRateLabel').innerText = 'Tốc độ (' + unit + '/giây)';
      if (!http) document.getElementById('pvEnvWrap').style.display = 'none';
    }

    // Điền lại toàn bộ form của chế độ đang chọn bằng cấu hình mẫu (bỏ cấu hình đã lưu trong trình duyệt)
    function fillDefaultSenderForm() {
      try { localStorage.removeItem(senderFormKey(senderMode)); } catch (e) {}
      restoreSenderForm();
      updateSenderVisibility();
      schedulePreview();
      setSenderMsg('Đã điền cấu hình mẫu cho ' + (SENDER_MODE_NAMES[senderMode] || senderMode) + '. Sửa IP / cổng cho đúng shipper rồi bấm Gửi.', 'ok');
    }

    // Ký token X-API-KEY bằng private key dán vào (agent.key), hiển thị để người dùng tự sao chép
    async function signHttpToken() {
      const keyEl = document.getElementById('sndHttpPrivKey');
      const out = document.getElementById('sndHttpSignResult');
      try {
        const data = await senderPost('/mock/admin/api/http_input/sign', {
          private_key: keyEl.value, payload: document.getElementById('sndHttpPayload').value.trim()
        });
        document.getElementById('sndHttpToken').innerText = data.token;
        document.getElementById('sndHttpTokenWrap').style.display = 'flex';
        out.innerHTML = 'md5 public key: <code style="font-family: var(--font-mono); color: #93c5fd;">'
          + senderEsc(data.public_key_md5) + '</code> (phải trùng: openssl x509 -in agent.crt -noout -pubkey | openssl md5). '
          + 'Token dùng lại được mãi tới khi đổi khóa agent.';
        setSenderMsg('Đã sinh token, bấm Sao chép để copy.', 'ok');
      } catch (e) {
        out.innerText = '';
        document.getElementById('sndHttpTokenWrap').style.display = 'none';
        setSenderMsg('Ký token lỗi: ' + e.message, 'err');
      }
    }

    async function loadHttpShipperEnv() {
      try {
        const res = await fetch('/mock/admin/api/http_input/env?format=shell');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        document.getElementById('pvEnv').innerText = await res.text();
        document.getElementById('pvEnvWrap').style.display = 'flex';
        setSenderMsg('Đã lấy PUB_KEY / SSL_CERT / SSL_KEY: sao chép và export trong terminal chạy shipper.', 'ok');
      } catch (e) {
        setSenderMsg('Không lấy được biến môi trường: ' + e.message, 'err');
      }
    }

    function senderEsc(v) {
      return String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function onSenderTransportChange() {
      updateSenderVisibility();
    }

    async function loadSenderDefaults() {
      if (senderDefaults) { schedulePreview(); return; }
      try {
        const res = await fetch('/mock/admin/api/sender/defaults');
        senderDefaults = await res.json();
        document.getElementById('sndLevel').innerHTML = senderDefaults.levels.map(l => `<option value="${l}">${l}</option>`).join('');
        let mode = 'syslog';
        try { mode = localStorage.getItem(SENDER_FORM_KEY + '.mode') || 'syslog'; } catch (e) {}
        if (mode !== 'syslog') {
          senderMode = mode;
          document.querySelectorAll('.sender-modes .sub-tab-btn').forEach(b => b.classList.remove('active'));
          document.getElementById('senderModeBtn-' + mode).classList.add('active');
        }
        restoreSenderForm();
        updateSenderVisibility();
        schedulePreview();
      } catch (e) {
        console.error(e);
      }
    }

    function fillDefaultSenderMessage() {
      if (!senderDefaults) return;
      document.getElementById('sndMessage').value = senderDefaults.forms[senderMode].message;
      document.getElementById('sndSplit').checked = true;
      schedulePreview();
    }

    function collectSenderConfig(countOverride) {
      const v = id => document.getElementById(id).value;
      const transport = senderTransport();
      const tcp = transport === 'tcp';
      const cfg = {
        type: senderMode,
        format: 'raw',                 // người dùng tự nhập cả header
        tcp_framing: 'newline',        // TCP: mỗi log kết thúc bằng xuống dòng
        host: v('sndHost').trim(),
        port: v('sndPort'),
        transport: transport,
        user: v('sndUser').trim(),
        action: v('sndAction').trim(),
        message: v('sndMessage'),
        split_lines: document.getElementById('sndSplit').checked,
        append_newline: tcp ? true : document.getElementById('sndNewline').checked,
        rate: v('sndRate'),
        count: v('sndCount'),
        duration: v('sndDuration')
      };
      let password = '';
      if (senderMode === 'redis') {
        cfg.key = v('sndRedisKey').trim();
        cfg.db = v('sndRedisDb');
        cfg.redis_command = v('sndRedisCommand');
        cfg.username = v('sndRedisUser').trim();
        password = v('sndRedisPassword');
      } else if (senderMode === 'beats') {
        cfg.batch_size = v('sndBeatsBatch');
        cfg.compress = document.getElementById('sndBeatsCompress').checked;
        cfg.tls = document.getElementById('sndBeatsTls').checked;
      } else if (senderMode === 'http') {
        cfg.path = v('sndHttpPath');
        cfg.batch_size = v('sndHttpBatch');
        cfg.tls = document.getElementById('sndHttpTls').checked;
        cfg.api_key = v('sndHttpApiKey').trim();
      } else if (senderMode !== 'syslog') {
        cfg.level = v('sndLevel');
        cfg.logger_name = v('sndLoggerName').trim();
        cfg.log_format = v('sndLogFormat');
      }
      try { localStorage.setItem(senderFormKey(senderMode), JSON.stringify(cfg)); } catch (e) {}   // không có mật khẩu
      if (password) cfg.password = password;
      if (countOverride) { cfg.count = countOverride; cfg.duration = 0; }
      return cfg;
    }

    function restoreSenderForm() {
      let cfg = null;
      try { cfg = JSON.parse(localStorage.getItem(senderFormKey(senderMode)) || 'null'); } catch (e) {}
      if (!cfg) cfg = (senderDefaults && senderDefaults.forms && senderDefaults.forms[senderMode]) || null;   // lần đầu: điền cấu hình mẫu
      if (!cfg) return;
      const map = { sndHost: 'host', sndPort: 'port', sndMessage: 'message',
                    sndUser: 'user', sndAction: 'action',
                    sndLevel: 'level', sndLoggerName: 'logger_name', sndLogFormat: 'log_format',
                    sndRedisKey: 'key', sndRedisDb: 'db', sndRedisCommand: 'redis_command', sndRedisUser: 'username',
                    sndRate: 'rate', sndCount: 'count', sndDuration: 'duration' };
      Object.keys(map).forEach(id => { if (cfg[map[id]] != null) document.getElementById(id).value = cfg[map[id]]; });
      if (senderMode === 'beats') {
        if (cfg.batch_size != null) document.getElementById('sndBeatsBatch').value = cfg.batch_size;
        document.getElementById('sndBeatsCompress').checked = cfg.compress !== false;
        document.getElementById('sndBeatsTls').checked = !!cfg.tls;
      } else if (senderMode === 'http') {
        if (cfg.batch_size != null) document.getElementById('sndHttpBatch').value = cfg.batch_size;
        if (cfg.path) document.getElementById('sndHttpPath').value = cfg.path;
        document.getElementById('sndHttpTls').checked = !!cfg.tls;
        document.getElementById('sndHttpApiKey').value = cfg.api_key || '';
      }
      if (senderMode === 'syslog' && cfg.transport) document.getElementById('sndTransport').value = cfg.transport;
      document.getElementById('sndSplit').checked = cfg.split_lines !== false;
      document.getElementById('sndNewline').checked = cfg.append_newline !== false;
    }

    function setSenderMsg(text, kind) {
      const el = document.getElementById('senderMsg');
      el.className = 'sender-msg ' + (kind || '');
      el.innerText = text || '';
    }

    async function senderPost(url, body) {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
      return data;
    }

    function schedulePreview() {
      clearTimeout(senderPreviewTimer);
      senderPreviewTimer = setTimeout(renderSenderPreview, 300);
    }

    // Xóa toàn bộ khung xem trước (tránh còn sót lệnh / code của tab trước)
    function clearSenderPreview(message, isError) {
      const summary = document.getElementById('pvSummary');
      summary.style.color = isError ? 'var(--danger)' : 'var(--text-dim)';
      summary.innerText = message;
      ['pvBashWrap', 'pvPythonWrap', 'pvLoopWrap', 'pvShipperWrap'].forEach(id => { document.getElementById(id).style.display = 'none'; });
      ['pvCommand', 'pvPython', 'pvLoop', 'pvShipper'].forEach(id => { document.getElementById(id).innerText = ''; });
      document.getElementById('pvPackets').innerText = '-';
      document.getElementById('pvNotes').innerHTML = '';
    }

    async function renderSenderPreview() {
      const summary = document.getElementById('pvSummary');
      const mode = senderMode;
      const cfg = collectSenderConfig();
      if (!cfg.host || !cfg.port) {
        clearSenderPreview('Điền IP và cổng để xem trước.', false);
        return;
      }
      try {
        const data = await senderPost('/mock/admin/api/sender/preview', cfg);
        if (mode !== senderMode) return;   // người dùng đã chuyển tab trong lúc chờ
        summary.style.color = '';
        summary.innerText = data.summary;
        document.getElementById('pvCommand').innerText = data.command;
        document.getElementById('pvBashWrap').style.display = (data.command && (!data.python_code || mode === 'beats')) ? 'flex' : 'none';
        document.getElementById('pvPythonWrap').style.display = data.python_code ? 'flex' : 'none';
        document.getElementById('pvPython').innerText = data.python_code || '';
        const loopWrap = document.getElementById('pvLoopWrap');
        loopWrap.style.display = (data.loop_command && !data.python_code) ? 'flex' : 'none';
        document.getElementById('pvLoop').innerText = data.loop_command || '';
        document.getElementById('pvShipperWrap').style.display = data.shipper_config ? 'flex' : 'none';
        document.getElementById('pvShipper').innerText = data.shipper_config || '';
        document.getElementById('pvPackets').innerHTML = data.packets.map((p, i) =>
          `<div style="margin-bottom: 0.5rem;"><span class="pv-meta">#${i + 1} &bull; ${p.bytes} byte</span>${SENDER_NL}${senderEsc(p.text)}${p.newline ? '<span class="pv-nl" title="ký tự xuống dòng">↵</span>' : ''}</div>`
        ).join('');
        document.getElementById('pvNotes').innerHTML = data.notes.map(n => `<li>${senderEsc(n)}</li>`).join('');
      } catch (e) {
        if (mode === senderMode) clearSenderPreview(e.message, true);
      }
    }

    function copySenderText(id) {
      const text = document.getElementById(id).innerText;
      const done = () => setSenderMsg('Đã sao chép lệnh.', 'ok');
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      } else {
        fallbackCopy(text, done);
      }
    }

    function fallbackCopy(text, done) {
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
      document.body.removeChild(ta);
    }

    async function startSender(countOverride) {
      try {
        const data = await senderPost('/mock/admin/api/sender/jobs', collectSenderConfig(countOverride));
        setSenderMsg('Đang gửi tới ' + data.job.target + ' (lượt ' + data.job.id + ')', 'ok');
        fetchSenderJobs();
      } catch (e) {
        setSenderMsg(e.message, 'err');
      }
    }

    async function stopSender(id) {
      await fetch(`/mock/admin/api/sender/jobs/${id}/stop`, { method: 'POST' });
      fetchSenderJobs();
    }

    async function removeSender(id) {
      await fetch(`/mock/admin/api/sender/jobs/${id}`, { method: 'DELETE' });
      fetchSenderJobs();
    }

    async function stopAllSenders() {
      await fetch('/mock/admin/api/sender/stop_all', { method: 'POST' });
      fetchSenderJobs();
    }

    // ===== GCP Pub/Sub =====
    function psMsg(text, kind) {
      const el = document.getElementById('psMsg');
      el.className = 'sender-msg ' + (kind || '');
      el.innerText = text || '';
    }

    async function fetchPubsub() {
      const st = document.getElementById('psStatus');
      try {
        const data = await (await fetch('/mock/admin/api/pubsub/status')).json();
        if (!data.running) {
          st.style.color = 'var(--danger)';
          st.innerText = 'Pub/Sub KHÔNG chạy: ' + (data.error || 'không rõ lý do');
          document.getElementById('psTopics').innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">-</td></tr>';
          return;
        }
        const ps = data.pubsub || {};
        st.style.color = '';
        st.innerText = `Đang chạy · gRPC cổng ${data.grpc_port} · đã ack ${ps.acked_total ?? 0} · chờ ack ${ps.unacked ?? 0}`;
        const topics = ps.topics || [];
        const sel = document.getElementById('psTopic');
        const cur = sel.value;
        sel.innerHTML = topics.map(t => `<option value="${senderEsc(t.topic)}">${senderEsc(t.topic.split('/').pop())}</option>`).join('');
        if (cur) sel.value = cur;
        document.getElementById('psTopics').innerHTML = topics.map(t => `<tr>
          <td style="font-family: var(--font-mono); font-size: 0.8rem;">${senderEsc(t.topic)}</td>
          <td style="font-family: var(--font-mono); font-size: 0.8rem;">${(t.subscriptions || []).map(x => senderEsc(x.split('/').pop())).join('<br>')}</td>
          <td style="font-family: var(--font-mono);">${t.published}</td>
          <td style="font-family: var(--font-mono);">${t.paused ? '<span style="color: var(--danger);">tạm dừng</span>' : t.rate + '/s'}</td>
          <td style="text-align: right;"><button class="btn" style="padding: 0.25rem 0.6rem;" onclick="togglePubsubGenerator('${senderEsc(t.topic)}', ${!t.paused})">${t.paused ? '▶ Chạy' : '⏸ Dừng'}</button></td>
        </tr>`).join('') || '<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">Chưa có topic</td></tr>';
      } catch (e) {
        st.style.color = 'var(--danger)';
        st.innerText = 'Lỗi lấy trạng thái: ' + e.message;
      }
    }

    async function fetchPubsubConfig() {
      const hostEl = document.getElementById('psHost');
      if (!hostEl.value) hostEl.value = window.location.hostname;
      try {
        const data = await (await fetch('/mock/admin/api/pubsub/config?host=' + encodeURIComponent(hostEl.value.trim()))).json();
        document.getElementById('psEnv').innerText = data.env;
        document.getElementById('psYml').innerText = data.cym_yml;
      } catch (e) { console.error(e); }
    }

    async function pubsubPost(body) {
      const res = await fetch('/mock/admin/api/pubsub/publish', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
      return data;
    }

    async function publishPubsub() {
      const topic = document.getElementById('psTopic').value;
      if (!topic) { psMsg('Chưa có topic nào', 'err'); return; }
      const lines = document.getElementById('psMessages').value.split(SENDER_NL).map(l => l.trim()).filter(Boolean);
      const body = { topic: topic };
      if (lines.length) body.messages = lines; else body.count = parseInt(document.getElementById('psCount').value || '1', 10);
      try {
        const data = await pubsubPost(body);
        psMsg(`Đã publish ${data.published} message vào ${topic.split('/').pop()}`, 'ok');
        fetchPubsub();
      } catch (e) { psMsg('Publish lỗi: ' + e.message, 'err'); }
    }

    async function togglePubsubGenerator(topic, pause) {
      try {
        await pubsubPost({ topic: topic, pause: pause, count: 0 });
        psMsg(pause ? 'Đã tạm dừng bộ sinh message' : 'Đã chạy lại bộ sinh message', 'ok');
        fetchPubsub();
      } catch (e) { psMsg('Lỗi: ' + e.message, 'err'); }
    }

    async function fetchSenderJobs() {
      try {
        const res = await fetch('/mock/admin/api/sender/jobs');
        const data = await res.json();
        const jobs = data.jobs || [];
        const running = jobs.filter(j => j.status === 'running' || j.status === 'starting').length;
        document.getElementById('senderRunningCount').innerText = running;
        const body = document.getElementById('senderJobsBody');
        if (!jobs.length) {
          body.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 2rem;">Chưa có lượt gửi nào</td></tr>';
          return;
        }
        const labels = { starting: 'Đang kết nối', running: 'Đang gửi', done: 'Xong', stopped: 'Đã dừng', error: 'Lỗi' };
        const fmtName = {};
        body.innerHTML = jobs.map(j => {
          const cls = j.status === 'starting' ? 'running' : j.status;
          const total = j.count ? ' / ' + j.count : '';
          const isRunning = j.status === 'running' || j.status === 'starting';
          const action = isRunning
            ? `<button class="btn btn-danger" style="padding: 0.25rem 0.6rem;" onclick="stopSender('${j.id}')">Dừng</button>`
            : `<button class="btn" style="padding: 0.25rem 0.6rem;" onclick="removeSender('${j.id}')">Xóa</button>`;
          const detail = j.last_error
            ? `<div class="job-last" style="color: #f87171;" title="${senderEsc(j.last_error)}">${senderEsc(j.last_error)}</div>`
            : `<div class="job-last" title="${senderEsc(j.last_message)}">${senderEsc(j.last_message)}</div>`;
          return `<tr>
            <td><span class="badge badge-job-${cls}">${labels[j.status] || j.status}</span><div class="job-last">${SENDER_MODE_NAMES[j.type] || j.type}${j.level ? ' &bull; ' + j.level : ''}</div></td>
            <td style="font-family: var(--font-mono); font-size: 0.8rem;">${senderEsc(j.target)}${detail}</td>
            <td style="font-family: var(--font-mono); white-space: nowrap;">${j.sent}${total}</td>
            <td style="font-family: var(--font-mono); color: ${j.errors ? 'var(--danger)' : 'inherit'};">${j.errors}</td>
            <td style="font-family: var(--font-mono); white-space: nowrap;">${j.actual_rate}/s</td>
            <td style="text-align: right;">${action}</td>
          </tr>`;
        }).join('');
      } catch (e) {
        console.error(e);
      }
    }

    // Auto polling
    setInterval(() => {
      fetchStatus();
      fetchLogs();
      fetchSenderJobs();
    }, 2000);

    // Initial load
    fetchStatus();
    fetchLogs();
    fetchScenarios();
    fetchRules();
  </script>
</body>
</html>"""
