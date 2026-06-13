import streamlit as st

def apply_custom_css():
    """Injects high-end, premium custom CSS variables and overrides for standard Streamlit widgets."""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        /* Global Typography Override */
        html, body, [class*="css"], .stApp {
            font-family: 'Outfit', sans-serif !important;
        }
        
        /* Main Heading Aesthetics */
        h1, h2, h3 {
            font-weight: 700 !important;
            letter-spacing: -0.02em !important;
            margin-bottom: 0.5rem !important;
        }
        
        /* Sidebar layout styling */
        section[data-testid="stSidebar"] {
            background-color: var(--secondary-background-color) !important;
            border-right: 1px solid rgba(128, 128, 128, 0.1) !important;
        }
        
        /* Custom Action Card Component */
        .action-card {
            background-color: var(--secondary-background-color);
            padding: 1.25rem;
            border-radius: 12px;
            border: 1px solid rgba(128, 128, 128, 0.15);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            margin-bottom: 0.85rem;
            transition: all 0.2s ease-in-out;
        }
        .action-card:hover {
            transform: translateY(-2px);
            border-color: var(--primary-color);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
        }
        
        .action-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        
        .action-card-title {
            font-weight: 700;
            font-size: 1.1rem;
            color: var(--text-color);
        }
        
        .action-card-body {
            font-size: 0.92rem;
            line-height: 1.5;
            color: var(--text-color);
            opacity: 0.9;
        }
        
        .action-card-footer {
            margin-top: 0.75rem;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        /* Status Badges */
        .badge {
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.75rem;
            display: inline-block;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .badge-success { background-color: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.25); }
        .badge-warning { background-color: rgba(245, 158, 11, 0.12); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.25); }
        .badge-danger { background-color: rgba(239, 68, 68, 0.12); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.25); }
        .badge-info { background-color: rgba(59, 130, 246, 0.12); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.25); }
        .badge-secondary { background-color: rgba(107, 114, 128, 0.12); color: #6b7280; border: 1px solid rgba(107, 114, 128, 0.25); }
        
        /* Metric values tweaks */
        div[data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 700 !important;
        }
        
        /* Compact Form Styling */
        div[data-testid="stForm"] {
            border-radius: 12px !important;
            border: 1px solid rgba(128, 128, 128, 0.15) !important;
            background-color: var(--secondary-background-color) !important;
            padding: 2rem !important;
        }
        
        /* Custom Dividers */
        .divider {
            height: 1px;
            background-color: rgba(128, 128, 128, 0.15);
            margin: 1.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)

def render_badge(text: str, badge_type: str = "secondary") -> str:
    """Returns the HTML for a styled status badge."""
    return f'<span class="badge badge-{badge_type}">{text}</span>'

def render_action_card(title: str, body_html: str, badge_text: str = "", badge_type: str = "secondary", footer_html: str = ""):
    """Renders a complete styled custom action card in Streamlit using HTML injection."""
    badge_html = render_badge(badge_text, badge_type) if badge_text else ""
    
    card_html = (
        f'<div class="action-card">'
        f'<div class="action-card-header">'
        f'<span class="action-card-title">{title}</span>'
        f'{badge_html}'
        f'</div>'
        f'<div class="action-card-body">'
        f'{body_html}'
        f'</div>'
    )
    
    if footer_html:
        card_html += (
            f'<div class="action-card-footer">'
            f'{footer_html}'
            f'</div>'
        )
        
    card_html += "</div>"
    st.markdown(card_html, unsafe_allow_html=True)
