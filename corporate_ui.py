"""Корпоративные стили интерфейса Streamlit."""

import streamlit as st

CORPORATE = {
    "navy_dark": "#0c2340",
    "navy_mid": "#163a63",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "gold": "#c9a227",
    "text_light": "#e2e8f0",
    "text_muted": "#94a3b8",
    "text_dark": "#0c2340",
    "btn_inactive_bg": "#061528",
    "btn_inactive_border": "rgba(255, 255, 255, 0.1)",
    "content_bg": "#f8fafc",
    "card_border": "rgba(255, 255, 255, 0.12)",
}


def render_pending_changes_banner(key_suffix):
    """Плашка «есть изменения» с кнопкой Rerun, как в Streamlit."""
    c = CORPORATE
    st.markdown(
        f"""
        <div class="pending-changes-banner">
            <span class="pending-changes-dot"></span>
            <span>Есть несохранённые изменения — нажмите <b>Rerun</b> или сохраните кандидатов</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _, btn_col = st.columns([5, 1])
    with btn_col:
        return st.button(
            "Rerun",
            key=f"pending_rerun_{key_suffix}",
            type="primary",
            use_container_width=True,
        )


def apply_corporate_ui():
    c = CORPORATE
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            html, body, [class*="css"] {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }}

            .stApp {{
                background-color: {c["content_bg"]};
            }}

            [data-testid="stSidebar"] {{
                background: linear-gradient(180deg, {c["navy_dark"]} 0%, {c["navy_mid"]} 100%);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }}

            [data-testid="stSidebar"] > div:first-child {{
                background: transparent;
            }}

            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] li,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] .stCaption {{
                color: {c["text_light"]};
            }}

            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3 {{
                color: #f8fafc !important;
                font-weight: 600;
                letter-spacing: -0.01em;
            }}

            [data-testid="stSidebar"] hr {{
                border-color: rgba(255, 255, 255, 0.1);
                margin: 1rem 0;
            }}

            .sidebar-brand {{
                padding: 0.25rem 0 1.25rem;
                margin-bottom: 0.5rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}

            .sidebar-brand-title {{
                font-size: 1.15rem;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: -0.02em;
            }}

            .sidebar-brand-subtitle {{
                font-size: 0.72rem;
                font-weight: 500;
                color: {c["gold"]};
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-top: 0.2rem;
            }}

            .sidebar-section-label {{
                font-size: 0.68rem;
                font-weight: 600;
                color: {c["text_muted"]};
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin: 0 0 0.65rem 0;
            }}

            .sidebar-config-card {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid {c["card_border"]};
                border-radius: 10px;
                padding: 0.75rem 0.9rem;
                margin-bottom: 0.5rem;
            }}

            .sidebar-config-row {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                gap: 0.75rem;
                padding: 0.35rem 0;
                border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            }}

            .sidebar-config-row:last-child {{
                border-bottom: none;
                padding-bottom: 0;
            }}

            .sidebar-config-row .label {{
                font-size: 0.78rem;
                color: {c["text_muted"]};
                flex-shrink: 0;
            }}

            .sidebar-config-row .value {{
                font-size: 0.78rem;
                color: {c["text_light"]};
                font-weight: 500;
                text-align: right;
                word-break: break-word;
            }}

            [data-testid="stSidebar"] a.client-zone-btn,
            [data-testid="stSidebar"] a.sidebar-link-btn {{
                display: block;
                width: 100%;
                box-sizing: border-box;
                padding: 0.6rem 0.85rem;
                margin-bottom: 0.4rem;
                background: {c["btn_inactive_bg"]};
                border: 1px solid {c["btn_inactive_border"]};
                border-radius: 8px;
                color: {c["text_light"]};
                text-decoration: none;
                font-size: 0.88rem;
                font-weight: 600;
                transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
            }}

            [data-testid="stSidebar"] a.client-zone-btn:hover,
            [data-testid="stSidebar"] a.sidebar-link-btn:hover {{
                background: {c["accent"]};
                border-color: {c["accent"]};
                color: #ffffff;
            }}

            [data-testid="stSidebar"] .sidebar-links-group {{
                margin-bottom: 0.25rem;
            }}

            [data-testid="stSidebar"] .stButton > button {{
                width: 100%;
                background: transparent !important;
                border: 1px solid rgba(255, 255, 255, 0.2) !important;
                color: {c["text_light"]} !important;
                border-radius: 8px !important;
                font-weight: 500 !important;
                transition: background 0.15s ease, border-color 0.15s ease !important;
            }}

            [data-testid="stSidebar"] .stButton > button:hover {{
                background: rgba(37, 99, 235, 0.18) !important;
                border-color: {c["accent"]} !important;
                color: #ffffff !important;
            }}

            [data-testid="stSidebarNav"],
            [data-testid="stSidebar"] nav,
            [data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {{
                display: none !important;
                visibility: hidden !important;
                height: 0 !important;
                margin: 0 !important;
                padding: 0 !important;
                overflow: hidden !important;
            }}

            .main .stButton > button,
            .main .stDownloadButton > button {{
                background-color: {c["accent"]} !important;
                border-color: {c["accent"]} !important;
                border-radius: 8px !important;
                font-weight: 500 !important;
            }}

            .main .stButton > button:hover,
            .main .stDownloadButton > button:hover {{
                background-color: {c["accent_hover"]} !important;
                border-color: {c["accent_hover"]} !important;
            }}

            [data-testid="stTabs"] button[data-baseweb="tab"],
            [data-testid="stTabs"] button[data-baseweb="tab"] p {{
                font-size: 1.05rem !important;
                font-weight: 500;
            }}

            [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
                color: {c["accent"]} !important;
                border-bottom-color: {c["accent"]} !important;
            }}

            .vacancy-candidates-count {{
                font-size: 1.15rem;
                color: {c["text_dark"]};
                margin: 0.25rem 0 1rem 0;
            }}

            .vacancy-candidates-count strong {{
                font-size: 1.35rem;
                color: {c["accent"]};
            }}

            .main .stButton > button[kind="secondary"] {{
                background-color: #ffffff !important;
                color: {c["text_dark"]} !important;
                border: 1px solid #cbd5e1 !important;
            }}

            .main .stButton > button[kind="secondary"]:hover {{
                border-color: {c["accent"]} !important;
                color: {c["accent"]} !important;
            }}

            .main .cand-stage-marker.cand-stage-rejected ~ div [data-testid="stExpander"],
            .main .element-container:has(.cand-stage-rejected) + .element-container [data-testid="stExpander"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-rejected) [data-testid="stExpander"] {{
                background-color: #fef2f2 !important;
                border: 1px solid #fecaca !important;
                border-radius: 8px !important;
            }}

            .main .cand-stage-marker.cand-stage-rejected ~ div [data-testid="stExpander"] summary,
            .main .element-container:has(.cand-stage-rejected) + .element-container [data-testid="stExpander"] summary,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-rejected) [data-testid="stExpander"] summary {{
                background-color: #fee2e2 !important;
                color: #991b1b !important;
                font-weight: 600 !important;
            }}

            .main .cand-stage-marker.cand-stage-rejected ~ div [data-testid="stExpander"] summary:hover,
            .main .element-container:has(.cand-stage-rejected) + .element-container [data-testid="stExpander"] summary:hover,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-rejected) [data-testid="stExpander"] summary:hover {{
                background-color: #fecaca !important;
                color: #7f1d1d !important;
            }}

            .main .cand-stage-marker.cand-stage-green ~ div [data-testid="stExpander"],
            .main .element-container:has(.cand-stage-green) + .element-container [data-testid="stExpander"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-green) [data-testid="stExpander"],
            .main .cand-stage-marker.cand-stage-offer ~ div [data-testid="stExpander"],
            .main .element-container:has(.cand-stage-offer) + .element-container [data-testid="stExpander"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-offer) [data-testid="stExpander"] {{
                background-color: #ecfdf5 !important;
                border: 1px solid #6ee7b7 !important;
                border-radius: 8px !important;
            }}

            .main .cand-stage-marker.cand-stage-green ~ div [data-testid="stExpander"] summary,
            .main .element-container:has(.cand-stage-green) + .element-container [data-testid="stExpander"] summary,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-green) [data-testid="stExpander"] summary,
            .main .cand-stage-marker.cand-stage-offer ~ div [data-testid="stExpander"] summary,
            .main .element-container:has(.cand-stage-offer) + .element-container [data-testid="stExpander"] summary,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-offer) [data-testid="stExpander"] summary {{
                background-color: #d1fae5 !important;
                color: #065f46 !important;
                font-weight: 600 !important;
            }}

            .main .cand-stage-marker.cand-stage-green ~ div [data-testid="stExpander"] summary:hover,
            .main .element-container:has(.cand-stage-green) + .element-container [data-testid="stExpander"] summary:hover,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-green) [data-testid="stExpander"] summary:hover,
            .main .cand-stage-marker.cand-stage-offer ~ div [data-testid="stExpander"] summary:hover,
            .main .element-container:has(.cand-stage-offer) + .element-container [data-testid="stExpander"] summary:hover,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-offer) [data-testid="stExpander"] summary:hover {{
                background-color: #a7f3d0 !important;
                color: #064e3b !important;
            }}

            .main .cand-stage-marker.cand-stage-yellow ~ div [data-testid="stExpander"],
            .main .element-container:has(.cand-stage-yellow) + .element-container [data-testid="stExpander"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-yellow) [data-testid="stExpander"] {{
                background-color: #fefce8 !important;
                border: 1px solid #fde047 !important;
                border-radius: 8px !important;
            }}

            .main .cand-stage-marker.cand-stage-yellow ~ div [data-testid="stExpander"] summary,
            .main .element-container:has(.cand-stage-yellow) + .element-container [data-testid="stExpander"] summary,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-yellow) [data-testid="stExpander"] summary {{
                background-color: #fef9c3 !important;
                color: #854d0e !important;
                font-weight: 600 !important;
            }}

            .main .cand-stage-marker.cand-stage-yellow ~ div [data-testid="stExpander"] summary:hover,
            .main .element-container:has(.cand-stage-yellow) + .element-container [data-testid="stExpander"] summary:hover,
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-yellow) [data-testid="stExpander"] summary:hover {{
                background-color: #fde68a !important;
                color: #713f12 !important;
            }}

            .main .bulk-success-msg {{
                background-color: #d1fae5;
                color: #065f46;
                padding: 0.75rem 1rem;
                border-radius: 8px;
                border: 1px solid #6ee7b7;
                font-weight: 600;
                margin-bottom: 1rem;
            }}

            .pending-changes-banner {{
                display: flex;
                align-items: center;
                gap: 0.6rem;
                background: linear-gradient(90deg, #fff7ed 0%, #ffedd5 100%);
                border: 1px solid #fdba74;
                border-radius: 8px;
                padding: 0.65rem 1rem;
                margin-bottom: 0.75rem;
                color: {c["text_dark"]};
                font-size: 0.92rem;
                font-weight: 500;
            }}

            .pending-changes-dot {{
                width: 0.55rem;
                height: 0.55rem;
                border-radius: 50%;
                background: #f97316;
                flex-shrink: 0;
                box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.25);
            }}

            .main .cand-stage-marker.cand-stage-rejected ~ div [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main .element-container:has(.cand-stage-rejected) + .element-container [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-rejected) [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
                background-color: #fff5f5 !important;
            }}

            .main .cand-stage-marker.cand-stage-green ~ div [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main .element-container:has(.cand-stage-green) + .element-container [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-green) [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main .cand-stage-marker.cand-stage-offer ~ div [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main .element-container:has(.cand-stage-offer) + .element-container [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-offer) [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
                background-color: #f0fdf4 !important;
            }}

            .main .cand-stage-marker.cand-stage-yellow ~ div [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main .element-container:has(.cand-stage-yellow) + .element-container [data-testid="stExpander"] [data-testid="stExpanderDetails"],
            .main [data-testid="stVerticalBlock"]:has(.cand-stage-yellow) [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
                background-color: #fffbeb !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
