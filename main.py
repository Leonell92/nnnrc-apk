# -*- coding: utf-8 -*-
import flet as ft
import requests
import threading
import time

API_BASE_URL = "https://leos-nrc-automation.onrender.com"

# ── Design Tokens ─────────────────────────────────────────────────────────────
WHITE          = "#FFFFFF"
BG_PAGE        = "#F7F9FA"
ACCENT         = "#16A34A"   # emerald green
ACCENT_LIGHT   = "#22C55E"   # mint green
TEXT_PRIMARY   = "#1F2937"   # charcoal
TEXT_SECONDARY = "#6B7280"   # muted gray
TEXT_HINT      = "#9CA3AF"
BORDER         = "#E5E7EB"   # ultra-light gray
CARD_SHADOW    = "#0000000D"

# Semantic status colours
STATUS_IDLE_BG   = "#F0FDF4"; STATUS_IDLE_FG   = "#15803D"; STATUS_IDLE_DOT   = ACCENT
STATUS_RUN_BG    = "#DCFCE7"; STATUS_RUN_FG    = "#166534"; STATUS_RUN_DOT    = ACCENT
STATUS_START_BG  = "#FEF9C3"; STATUS_START_FG  = "#854D0E"; STATUS_START_DOT  = "#EAB308"
STATUS_DONE_BG   = "#F0FDF4"; STATUS_DONE_FG   = "#15803D"; STATUS_DONE_DOT   = ACCENT
STATUS_ERR_BG    = "#FEE2E2"; STATUS_ERR_FG    = "#DC2626"; STATUS_ERR_DOT    = "#DC2626"

LOG_DEFAULT = "#374151"
LOG_SUCCESS = "#15803D"
LOG_ERROR   = "#DC2626"
LOG_WARN    = "#92400E"
LOG_INFO    = "#1D4ED8"


def main(page: ft.Page):
    # ── Page Setup ────────────────────────────────────────────────────────────
    page.title         = "NRC Automator"
    page.theme_mode    = ft.ThemeMode.LIGHT
    page.window_width  = 420
    page.window_height = 820
    page.window_resizable = False
    page.padding       = 0
    page.bgcolor       = WHITE
    page.fonts         = {
        "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    }
    page.theme = ft.Theme(
        font_family="Inter",
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            surface=WHITE,
            background=BG_PAGE,
        ),
    )

    state = {"job_id": None, "is_running": False}

    # ═══════════════════════════════════════════════════════════════════════════
    # SHARED HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Status widgets ────────────────────────────────────────────────────────
    _status_dot   = ft.Container(width=7, height=7, bgcolor=STATUS_IDLE_DOT,  border_radius=4)
    _status_label = ft.Text("IDLE", size=11, weight=ft.FontWeight.W_600, color=STATUS_IDLE_FG)
    status_badge  = ft.Container(
        content=ft.Row(
            [_status_dot, _status_label],
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=STATUS_IDLE_BG,
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=11, vertical=5),
    )

    completed_text = ft.Text(
        "0 / 0 tasks",
        size=13,
        color=TEXT_SECONDARY,
        weight=ft.FontWeight.W_500,
    )

    progress_ring = ft.ProgressRing(
        visible=False, color=ACCENT,
        width=15, height=15, stroke_width=2,
    )

    def set_status(label, bg, fg, dot):
        _status_label.value   = label
        _status_label.color   = fg
        _status_dot.bgcolor   = dot
        status_badge.bgcolor  = bg
        page.update()

    # ── Log panel ─────────────────────────────────────────────────────────────
    log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=0)

    empty_state = ft.Container(
        visible=True,
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(
                        ft.icons.RECEIPT_LONG_OUTLINED,
                        color="#D1D5DB",
                        size=34,
                    ),
                    margin=ft.margin.only(bottom=10),
                ),
                ft.Text(
                    "No execution logs yet.",
                    size=13,
                    color=TEXT_SECONDARY,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Your activity will appear here.",
                    size=12,
                    color=TEXT_HINT,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        ),
    )

    # Stack: empty_state sits behind the log list
    log_body = ft.Stack(
        [empty_state, log_list],
        expand=True,
    )

    def append_log(msg: str, color: str = LOG_DEFAULT, do_update: bool = True):
        if empty_state.visible and len(log_list.controls) == 0:
            empty_state.visible = False
        log_list.controls.append(
            ft.Container(
                content=ft.Text(
                    msg, size=12, color=color, selectable=True,
                    font_family="Inter",
                ),
                padding=ft.padding.symmetric(vertical=1),
            )
        )
        if do_update:
            page.update()

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 1 — BOT
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Input fields ──────────────────────────────────────────────────────────
    def _field_style():
        return dict(
            border_radius=14,
            border_color=BORDER,
            focused_border_color=ACCENT,
            border_width=1.5,
            focused_border_width=2,
            bgcolor=WHITE,
            focused_bgcolor=WHITE,
            color=TEXT_PRIMARY,
            cursor_color=ACCENT,
            label_style=ft.TextStyle(color=TEXT_HINT, size=13),
            text_style=ft.TextStyle(size=14, color=TEXT_PRIMARY),
        )

    phone_input = ft.TextField(
        label="Phone Number",
        prefix_icon=ft.icons.PHONE_OUTLINED,
        keyboard_type=ft.KeyboardType.PHONE,
        **_field_style(),
    )

    password_input = ft.TextField(
        label="Password",
        prefix_icon=ft.icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        **_field_style(),
    )

    # ── Primary button ────────────────────────────────────────────────────────
    start_btn = ft.ElevatedButton(
        content=ft.Row(
            [
                ft.Icon(ft.icons.PLAY_ARROW_ROUNDED, color=WHITE, size=17),
                ft.Text(
                    "Start Automating",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=WHITE,
                    font_family="Inter",
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor={
                "":         ACCENT,
                "hovered":  "#15803D",
                "pressed":  "#166534",
                "disabled": "#D1D5DB",
            },
            overlay_color="#FFFFFF18",
            elevation={"": 2, "hovered": 5, "disabled": 0},
            shadow_color="#16A34A30",
            padding=ft.padding.symmetric(vertical=15),
        ),
        on_click=lambda e: start_clicked(e),
        width=float("inf"),
    )

    # ── Polling ───────────────────────────────────────────────────────────────
    def poll_status():
        seen = 0
        while state["is_running"] and state["job_id"]:
            try:
                resp = requests.get(
                    f"{API_BASE_URL}/status/{state['job_id']}", timeout=10
                )
                if resp.status_code == 200:
                    data       = resp.json()
                    job_status = data.get("status", "running")
                    completed  = data.get("completed", 0)
                    total      = data.get("total", 0)
                    logs       = data.get("log", [])

                    completed_text.value = f"{completed} / {total} tasks"

                    for entry in logs[seen:]:
                        if "✅" in entry or "done" in entry.lower() or "success" in entry.lower():
                            col = LOG_SUCCESS
                        elif "❌" in entry or "error" in entry.lower() or "fail" in entry.lower():
                            col = LOG_ERROR
                        elif any(x in entry for x in ("⏳", "⏸️", "🔄", "📡", "📋")):
                            col = LOG_WARN
                        elif any(x in entry for x in ("🤖", "🔑", "🏁")):
                            col = LOG_INFO
                        else:
                            col = LOG_DEFAULT
                        append_log(entry, col, do_update=False)
                        seen += 1

                    if job_status in ("finished", "error"):
                        state["is_running"]   = False
                        start_btn.disabled    = False
                        progress_ring.visible = False
                        if job_status == "finished":
                            set_status("DONE ✓", STATUS_DONE_BG, STATUS_DONE_FG, STATUS_DONE_DOT)
                        else:
                            set_status("ERROR", STATUS_ERR_BG, STATUS_ERR_FG, STATUS_ERR_DOT)

                    page.update()
                    if not state["is_running"]:
                        break

            except Exception as ex:
                append_log(f"Poll error: {ex}", LOG_ERROR, do_update=True)

            time.sleep(3)

    def start_clicked(e):
        phone = phone_input.value.strip()
        pwd   = password_input.value.strip()
        if not phone or not pwd:
            append_log("⚠️  Enter phone and password first.", LOG_WARN)
            return

        # Reset UI
        start_btn.disabled    = True
        progress_ring.visible = True
        log_list.controls.clear()
        empty_state.visible   = False
        completed_text.value  = "0 / 0 tasks"
        set_status("STARTING", STATUS_START_BG, STATUS_START_FG, STATUS_START_DOT)
        page.update()

        try:
            append_log("📡  Connecting to automation server...")
            resp = requests.post(
                f"{API_BASE_URL}/start",
                json={"phone": phone, "password": pwd},
                timeout=20,
            )
            data = resp.json()
            if resp.status_code == 200 and "job_id" in data:
                state["job_id"]     = data["job_id"]
                state["is_running"] = True
                append_log(f"✅  Session started · ID: {data['job_id'][:8]}…", LOG_SUCCESS)
                set_status("RUNNING", STATUS_RUN_BG, STATUS_RUN_FG, STATUS_RUN_DOT)
                threading.Thread(target=poll_status, daemon=True).start()
            else:
                append_log(f"❌  Failed: {data.get('error', data)}", LOG_ERROR)
                start_btn.disabled    = False
                progress_ring.visible = False
                set_status("IDLE", STATUS_IDLE_BG, STATUS_IDLE_FG, STATUS_IDLE_DOT)
        except Exception as ex:
            append_log(f"❌  Network error: {ex}", LOG_ERROR)
            start_btn.disabled    = False
            progress_ring.visible = False
            set_status("IDLE", STATUS_IDLE_BG, STATUS_IDLE_FG, STATUS_IDLE_DOT)

        page.update()

    # ── Bot Tab Layout ────────────────────────────────────────────────────────
    bot_tab = ft.Container(
        bgcolor=BG_PAGE,
        expand=True,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[

                # ── Header bar ────────────────────────────────────────────────
                ft.Container(
                    bgcolor=WHITE,
                    padding=ft.padding.fromLTRB(22, 24, 22, 20),
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                    content=ft.Row(
                        [
                            # Icon badge
                            ft.Container(
                                content=ft.Icon(
                                    ft.icons.BOLT_OUTLINED,
                                    color=ACCENT,
                                    size=22,
                                ),
                                bgcolor="#F0FDF4",
                                border_radius=10,
                                padding=9,
                                border=ft.border.all(1, "#D1FAE5"),
                            ),
                            # Title + subtitle
                            ft.Column(
                                [
                                    ft.Text(
                                        "NRC Automator",
                                        size=18,
                                        weight=ft.FontWeight.W_700,
                                        color=TEXT_PRIMARY,
                                        font_family="Inter",
                                    ),
                                    ft.Text(
                                        "by Leo Emmanuel",
                                        size=11,
                                        color=TEXT_SECONDARY,
                                        weight=ft.FontWeight.W_400,
                                        font_family="Inter",
                                    ),
                                ],
                                spacing=1,
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                        ],
                        spacing=13,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),

                # ── Scrollable body ───────────────────────────────────────────
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[

                            # ── Credentials card ──────────────────────────────
                            ft.Container(
                                margin=ft.margin.fromLTRB(16, 20, 16, 0),
                                content=ft.Container(
                                    bgcolor=WHITE,
                                    border_radius=16,
                                    padding=ft.padding.fromLTRB(18, 16, 18, 20),
                                    border=ft.border.all(1, BORDER),
                                    shadow=ft.BoxShadow(
                                        spread_radius=0, blur_radius=14,
                                        color=CARD_SHADOW, offset=ft.Offset(0, 3),
                                    ),
                                    content=ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Container(
                                                        width=3, height=14,
                                                        bgcolor=ACCENT,
                                                        border_radius=2,
                                                    ),
                                                    ft.Text(
                                                        "ACCOUNT CREDENTIALS",
                                                        size=10,
                                                        weight=ft.FontWeight.W_700,
                                                        color=TEXT_SECONDARY,
                                                        letter_spacing=1.2,
                                                        font_family="Inter",
                                                    ),
                                                ],
                                                spacing=8,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                            ft.Container(height=14),
                                            phone_input,
                                            ft.Container(height=12),
                                            password_input,
                                        ],
                                        spacing=0,
                                    ),
                                ),
                            ),

                            # ── Action button ──────────────────────────────────
                            ft.Container(
                                margin=ft.margin.fromLTRB(16, 14, 16, 0),
                                content=start_btn,
                            ),

                            # ── Status row ────────────────────────────────────
                            ft.Container(
                                margin=ft.margin.fromLTRB(16, 12, 16, 0),
                                content=ft.Container(
                                    bgcolor=WHITE,
                                    border_radius=12,
                                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                                    border=ft.border.all(1, BORDER),
                                    content=ft.Row(
                                        [
                                            progress_ring,
                                            status_badge,
                                            ft.Container(expand=True),
                                            ft.Icon(
                                                ft.icons.TASK_ALT_OUTLINED,
                                                color=TEXT_HINT,
                                                size=14,
                                            ),
                                            completed_text,
                                        ],
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                ),
                            ),

                            # ── Execution log card ─────────────────────────────
                            ft.Container(
                                margin=ft.margin.fromLTRB(16, 16, 16, 20),
                                content=ft.Container(
                                    bgcolor=WHITE,
                                    border_radius=16,
                                    padding=ft.padding.fromLTRB(18, 16, 18, 16),
                                    border=ft.border.all(1, BORDER),
                                    shadow=ft.BoxShadow(
                                        spread_radius=0, blur_radius=14,
                                        color=CARD_SHADOW, offset=ft.Offset(0, 3),
                                    ),
                                    height=270,
                                    content=ft.Column(
                                        [
                                            # Log header
                                            ft.Row(
                                                [
                                                    ft.Container(
                                                        content=ft.Icon(
                                                            ft.icons.TERMINAL_OUTLINED,
                                                            color=ACCENT,
                                                            size=14,
                                                        ),
                                                        bgcolor="#F0FDF4",
                                                        border_radius=6,
                                                        padding=5,
                                                    ),
                                                    ft.Text(
                                                        "Execution Log",
                                                        size=12,
                                                        weight=ft.FontWeight.W_600,
                                                        color=TEXT_PRIMARY,
                                                        font_family="Inter",
                                                    ),
                                                    ft.Container(expand=True),
                                                    # Live indicator dot
                                                    ft.Container(
                                                        content=ft.Text(
                                                            "LIVE",
                                                            size=9,
                                                            weight=ft.FontWeight.W_700,
                                                            color=ACCENT,
                                                            letter_spacing=0.8,
                                                        ),
                                                        bgcolor="#F0FDF4",
                                                        border_radius=8,
                                                        padding=ft.padding.symmetric(
                                                            horizontal=7, vertical=3
                                                        ),
                                                        border=ft.border.all(1, "#BBF7D0"),
                                                    ),
                                                ],
                                                spacing=8,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            ),
                                            # Divider
                                            ft.Container(
                                                height=1,
                                                bgcolor=BORDER,
                                                margin=ft.margin.symmetric(vertical=10),
                                            ),
                                            # Log body (empty state + list)
                                            ft.Container(
                                                expand=True,
                                                content=log_body,
                                            ),
                                        ],
                                        spacing=0,
                                        expand=True,
                                    ),
                                ),
                            ),

                        ],
                    ),
                ),
            ],
        ),
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # TAB 2 — LIVE SITE
    # ═══════════════════════════════════════════════════════════════════════════
    webview = ft.WebView(
        url="https://nnnrc.com/#/mytask",
        expand=True,
        on_page_started=lambda e: None,
    )

    live_site_tab = ft.Container(
        expand=True,
        bgcolor=WHITE,
        content=ft.Column(
            [
                # Sub-header bar
                ft.Container(
                    bgcolor=WHITE,
                    padding=ft.padding.symmetric(horizontal=20, vertical=13),
                    border=ft.border.only(bottom=ft.BorderSide(1, BORDER)),
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.icons.LANGUAGE_OUTLINED,
                                    color=ACCENT,
                                    size=15,
                                ),
                                bgcolor="#F0FDF4",
                                border_radius=7,
                                padding=6,
                                border=ft.border.all(1, "#D1FAE5"),
                            ),
                            ft.Text(
                                "nnnrc.com  ·  Live View",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=TEXT_PRIMARY,
                                font_family="Inter",
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                webview,
            ],
            spacing=0,
            expand=True,
        ),
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # TABS SHELL
    # ═══════════════════════════════════════════════════════════════════════════
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=180,
        expand=True,
        tabs=[
            ft.Tab(
                text="Bot",
                icon=ft.icons.SMART_TOY_OUTLINED,
                content=bot_tab,
            ),
            ft.Tab(
                text="Live Site",
                icon=ft.icons.LANGUAGE_OUTLINED,
                content=live_site_tab,
            ),
        ],
        indicator_color=ACCENT,
        label_color=ACCENT,
        unselected_label_color=TEXT_SECONDARY,
        divider_color=BORDER,
    )

    page.add(tabs)


if __name__ == "__main__":
    ft.app(target=main)
