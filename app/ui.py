"""
Shared UI helpers: persistent footer and a feedback / report-issue widget.

These helpers are deliberately decoupled from any page logic so they can be
imported from `main.py` and from every page module without affecting the
visualizations, tables, or data flow.

The feedback widget posts to FormSubmit.co's AJAX endpoint, which forwards
the message to the configured email address. No SMTP credentials are stored
in the repo.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

import streamlit as st


FEEDBACK_EMAIL = "stoicaelias2003@gmail.com"
GITHUB_URL = "https://github.com/wood11nho/transfer-analysis-superliga"
PROJECT_NAME = "Superliga Transfer Analytics"
AUTHOR_NAME = "Stoica Elias"
INTERNSHIP_ATTRIBUTION = "Built during an internship at the Romanian Football Federation (FRF)."

FORMSUBMIT_ENDPOINT = f"https://formsubmit.co/ajax/{FEEDBACK_EMAIL}"


def _post_feedback(payload: dict[str, Any]) -> tuple[bool, str]:
    """POST the feedback payload to FormSubmit. Returns (ok, message)."""
    try:
        import requests  # imported lazily so the app still runs if missing
    except ImportError:
        return (
            False,
            "The `requests` package is not installed. Add `requests` to requirements.txt.",
        )

    try:
        resp = requests.post(
            FORMSUBMIT_ENDPOINT,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=10,
        )
    except Exception as exc:  # network / DNS / TLS errors
        return False, f"Could not reach the feedback service ({exc})."

    if resp.status_code in (200, 201):
        return True, "Thanks! Your feedback was sent."
    return (
        False,
        f"Feedback service returned status {resp.status_code}. Please try again later.",
    )


def render_feedback_widget(location: str = "sidebar") -> None:
    """
    Render a collapsible feedback / report-issue form.

    location:
        "sidebar" — render in the left sidebar (default, recommended)
        "main"    — render inline in the main page area
    """
    container = st.sidebar if location == "sidebar" else st

    with container.expander("💬 Feedback / Report an issue", expanded=False):
        st.caption(
            "Spotted a bug, wrong number, or have a suggestion? "
            "Send a short note — it goes straight to the maintainer's inbox."
        )

        with st.form("feedback_form", clear_on_submit=True):
            name = st.text_input("Your name (optional)", max_chars=80)
            email = st.text_input("Your email (optional, for reply)", max_chars=120)
            category = st.selectbox(
                "Type",
                ["Bug / data issue", "Feature suggestion", "General feedback", "Other"],
            )
            message = st.text_area(
                "Message *",
                max_chars=2000,
                height=140,
                placeholder="Tell us what you saw, what page you were on, and what you expected.",
            )
            submitted = st.form_submit_button("Send")

            if submitted:
                if not message or not message.strip():
                    st.warning("Please add a message before sending.")
                    return

                payload = {
                    "name": name.strip() or "(anonymous)",
                    "email": email.strip() or "(not provided)",
                    "category": category,
                    "message": message.strip(),
                    "page": _current_page_label(),
                    "_subject": f"[{PROJECT_NAME}] {category}",
                    "_template": "table",
                    "_captcha": "false",
                }
                if email.strip():
                    payload["_replyto"] = email.strip()

                with st.spinner("Sending feedback…"):
                    ok, msg = _post_feedback(payload)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
                    st.caption(
                        "If the issue persists you can also open a GitHub issue: "
                        f"[{GITHUB_URL}/issues]({GITHUB_URL}/issues)"
                    )


def _current_page_label() -> str:
    """Best-effort label for the page the feedback was sent from."""
    try:
        # Streamlit >= 1.30 exposes the current page title via st.session_state
        ctx = st.session_state.get("_page_title")
        if ctx:
            return str(ctx)
    except Exception:
        pass
    return "unknown"


def render_footer() -> None:
    """Render a small, unobtrusive footer at the bottom of the page."""
    year = _dt.datetime.now().year
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align:center; color:#888; font-size:0.85rem; line-height:1.5; padding-top:0.25rem;">
            <strong>{PROJECT_NAME}</strong> · {INTERNSHIP_ATTRIBUTION}<br>
            © {year} {AUTHOR_NAME} ·
            <a href="{GITHUB_URL}" target="_blank" style="color:#888; text-decoration:underline;">GitHub</a> ·
            <a href="{GITHUB_URL}/issues" target="_blank" style="color:#888; text-decoration:underline;">Report an issue</a><br>
            <span style="color:#aaa;">Data: Transfermarkt · For research and educational purposes.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_chrome(page_title: str | None = None) -> None:
    """
    Convenience: render sidebar feedback + footer in one call.

    Call this at the END of a page's `main()` so it appears after all content.
    """
    if page_title:
        st.session_state["_page_title"] = page_title
    render_feedback_widget(location="sidebar")
    render_footer()
