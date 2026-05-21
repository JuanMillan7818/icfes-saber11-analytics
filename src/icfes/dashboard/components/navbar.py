import streamlit as st


def render_navbar():
    st.markdown(
        """
<div class="navbar">
    <span class="navbar-brand">📊 ICFES Saber 11</span>
    <div class="nav-spacer"></div>
    <span style="color:#475569; font-size:0.78rem; letter-spacing:0.05em;">Colombia · 2015–2025 · ~4.3 GB</span>
</div>
""",
        unsafe_allow_html=True,
    )
