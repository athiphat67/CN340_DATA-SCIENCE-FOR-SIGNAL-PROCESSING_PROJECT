"""
core/dashboard_css.py
=====================
Global CSS override สำหรับ Gradio
Apply design system จาก code.html + DESIGN.md ให้กับ Gradio components เอง
(input, dropdown, button, tab, textbox)

ใช้งาน:
    from core.dashboard_css import DASHBOARD_CSS
    with gr.Blocks(css=DASHBOARD_CSS) as demo:
        ...
"""
DASHBOARD_CSS = """
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif:wght@700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap');

/* ── Design tokens ── */
:root {
    --surface:           #f6fafe;
    --surface-low:       #f0f4f8;
    --surface-high:      #e4e9ed;
    --surface-lowest:    #ffffff;
    --surface-container: #eaeef2;
    --primary:           #0058be;
    --primary-container: #2170e4;
    --success:           #10b981;
    --error:             #ef4444;
    --warning:           #f59e0b;
    --on-surface:        #171c1f;
    --on-surface-var:    #424754;
    --outline-var:       #c2c6d6;
    --inverse-surface:   #1e293b;
    --shadow-ambient:    0px 12px 32px rgba(0,88,190,0.06);
    --shadow-float:      0px 24px 48px rgba(0,88,190,0.10);
    --font-body:         'Inter', sans-serif;
    --font-mono:         'IBM Plex Mono', monospace;
    --font-headline:     'Noto Serif', serif;
}

/* ── Page background ── */
body, .gradio-container {
    background: var(--surface) !important;
    font-family: var(--font-body) !important;
    color: var(--on-surface) !important;
}

/* ── Remove default Gradio "white box" wrapper ── */
.gradio-container > .main {
    background: transparent !important;
}
.block {
    background: transparent !important;
    border: none !important;
    
}

/* ── Tab navigation ── */
.tab-nav {
    background: transparent !important;
    border-bottom: 1px solid var(--surface-container) !important;
    padding: 0 4px !important;
    gap: 0 !important;
}
.tab-nav button {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--on-surface-var) !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    padding: 10px 18px !important;
    transition: color 0.15s, border-color 0.15s !important;
}
.tab-nav button.selected {
    color: var(--primary) !important;
    border-bottom-color: var(--primary) !important;
    font-weight: 600 !important;
}
.tab-nav button:hover:not(.selected) {
    color: var(--on-surface) !important;
}

/* ── Textbox / Number inputs ── */
.gr-box, .gr-text-input, textarea, input[type="text"],
input[type="number"], .gr-input {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    background: var(--surface-low) !important;
    border: none !important;
    border-radius: 8px !important;
    color: var(--on-surface) !important;
    transition: background 0.15s !important;
}
.gr-box:focus-within, textarea:focus, input:focus {
    background: var(--surface-lowest) !important;
    outline: 2px solid rgba(0,88,190,0.20) !important;
    outline-offset: 0 !important;
}

/* Label above inputs */
label > span, .gr-label span {
    font-family: var(--font-body) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: var(--on-surface-var) !important;
}

/* ── Dropdown ── */
.gr-dropdown select, select {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    background: var(--surface-low) !important;
    border: none !important;
    border-radius: 8px !important;
    color: var(--on-surface) !important;
}

/* ── Checkbox + CheckboxGroup ── */
.gr-checkbox-group label, .gr-checkbox label {
    font-family: var(--font-body) !important;
    font-size: 12px !important;
    color: var(--on-surface) !important;
}
input[type="checkbox"]:checked {
    accent-color: var(--primary) !important;
}

/* ── Primary button (variant="primary") ── */
.gr-button-primary, button.primary {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    background: linear-gradient(135deg, var(--primary), var(--primary-container)) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    box-shadow: 0 4px 14px rgba(0,88,190,0.25) !important;
    transition: opacity 0.15s, transform 0.1s !important;
    cursor: pointer !important;
}
.gr-button-primary:hover, button.primary:hover {
    opacity: 0.92 !important;
}
.gr-button-primary:active, button.primary:active {
    transform: scale(0.97) !important;
}

/* ── Secondary button ── */
.gr-button-secondary, button.secondary {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    background: var(--surface-high) !important;
    color: var(--on-surface) !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 20px !important;
    transition: background 0.15s !important;
}
.gr-button-secondary:hover, button.secondary:hover {
    background: var(--surface-highest) !important;
}

/* ── Markdown headings ── */
.gr-markdown h1, .gr-markdown h2 {
    font-family: var(--font-headline) !important;
    color: var(--on-surface) !important;
}
.gr-markdown h3, .gr-markdown h4 {
    font-family: var(--font-body) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: var(--on-surface-var) !important;
}
.gr-markdown p {
    font-family: var(--font-body) !important;
    font-size: 13px !important;
    color: var(--on-surface-var) !important;
}

/* ── Code / mono output ── */
.gr-markdown code, code, pre {
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
    background: var(--surface-container) !important;
    color: var(--on-surface) !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
}

/* ── Row spacing ── */
.gr-row {
    gap: 14px !important;
}

/* ── Toast / status bar ── */
#stats-bar {
    padding: 10px 14px !important;
    background: var(--surface-low) !important;
    border-radius: 10px !important;
    font-family: var(--font-mono) !important;
    font-size: 12px !important;
}

/* ── Scrollbars ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--outline-var);
    border-radius: 99px;
}

#navbar {
    background: #ffffff;
    padding: 12px 24px;
    border-bottom: 1px solid #eee;
}

#sidebar {
    background: #f8fafc;
    padding: 16px;
    border-radius: 12px;
}

.card {
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0px 10px 30px rgba(0,0,0,0.05);
}

.strong-buy {
    background: #10b981;
    color: white;
    border-radius: 16px;
    padding: 24px;
    text-align: center;
}

/* 1. Hide the Light/Dark/System buttons in the settings modal */
input[value="light"], input[value="dark"], input[value="system"] {
    display: none !important;
}
label:has(input[value="dark"]), label:has(input[value="light"]), label:has(input[value="system"]) {
    display: none !important;
}

/* 2. Force Dark Mode to render exactly like Light Mode */
.dark {
    --background-fill-primary: #ffffff !important;
    --background-fill-secondary: #f6fafe !important;
    --body-background-fill: #f6fafe !important;
    --body-text-color: #171c1f !important;
    --color-accent-soft: #eaeef2 !important;
    --border-color-primary: #eaeef2 !important;
    --block-background-fill: #ffffff !important;
}
body.dark {
    background-color: #f6fafe !important;
    color: #171c1f !important;
}

"""










