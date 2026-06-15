import flet as ft
import requests
import threading
import time

API_BASE_URL = "https://leos-nrc-automation.onrender.com"


def main(page: ft.Page):
    page.title        = "NNNRC Automator"
    page.theme_mode   = ft.ThemeMode.DARK
    page.window_width  = 420
    page.window_height = 820
    page.padding       = 0
    page.bgcolor       = "#0d0d0d"
    page.fonts         = {"Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap"}
    page.theme         = ft.Theme(font_family="Inter")

    state = {"job_id": None, "is_running": False, "last_log_count": 0}

    # ──────────────────────────────────────────────
    # TAB 1 — Automation controls
    # ──────────────────────────────────────────────
    phone_input = ft.TextField(
        label="Phone Number",
        prefix_icon=ft.icons.PHONE_ANDROID,
        border_radius=14,
        keyboard_type=ft.KeyboardType.PHONE,
        focused_border_color="#4fa3ff",
        bgcolor="#1a1a2e",
        border_color="#2a2a4a",
        color="white",
    )

    password_input = ft.TextField(
        label="Password",
        prefix_icon=ft.icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
        border_radius=14,
        focused_border_color="#4fa3ff",
        bgcolor="#1a1a2e",
        border_color="#2a2a4a",
        color="white",
    )

    progress_ring = ft.ProgressRing(visible=False, color="#4fa3ff", width=20, height=20)

    status_badge = ft.Container(
        content=ft.Text("IDLE", size=11, weight=ft.FontWeight.BOLD, color="white"),
        bgcolor="#333355",
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=12, vertical=4),
    )

    completed_text = ft.Text("0 / 0 tasks", size=14, color="#aaaacc")

    stats_row = ft.Row(
        [progress_ring, status_badge, completed_text],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
    )

    log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)

    def append_log(msg: str, color: str = "#ccccdd", do_update: bool = True):
        log_view.controls.append(
            ft.Text(msg, size=12, color=color, selectable=True)
        )
        if do_update:
            page.update()

    def set_status(label: str, color: str = "#4fa3ff"):
        status_badge.content.value = label
        status_badge.bgcolor = color
        page.update()

    def poll_status():
        seen_logs = 0
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

                    # Batch all UI changes — only one page.update() at the end
                    completed_text.value = f"{completed} / {total} tasks"

                    new_entries = logs[seen_logs:]
                    for entry in new_entries:
                        if "\u2705" in entry:
                            color = "#4ade80"
                        elif ("\u274c" in entry or "error" in entry.lower()
                              or "fail" in entry.lower()):
                            color = "#f87171"
                        elif "\u23f3" in entry or "Fetch" in entry or "API code" in entry:
                            color = "#facc15"
                        else:
                            color = "#ccccdd"
                        append_log(entry, color, do_update=False)
                        seen_logs += 1

                    if job_status in ("finished", "error"):
                        state["is_running"] = False
                        start_btn.disabled    = False
                        progress_ring.visible = False
                        lbl   = "DONE \u2713" if job_status == "finished" else "ERROR \u2717"
                        clr   = "#4ade80"  if job_status == "finished" else "#f87171"
                        status_badge.content.value = lbl
                        status_badge.bgcolor       = clr

                    # Single update for everything
                    page.update()

                    if not state["is_running"]:
                        break

            except Exception as ex:
                append_log(f"Poll error: {ex}", "#f87171", do_update=True)

            time.sleep(3)

    def start_clicked(e):
        phone = phone_input.value.strip()
        pwd   = password_input.value.strip()
        if not phone or not pwd:
            append_log("⚠️ Enter phone and password first.", "#facc15")
            return

        start_btn.disabled    = True
        progress_ring.visible = True
        log_view.controls.clear()
        set_status("STARTING", "#4fa3ff")
        completed_text.value = "0 / 0 tasks"
        page.update()

        try:
            append_log("📡 Sending start request to API...")
            resp = requests.post(
                f"{API_BASE_URL}/start",
                json={"phone": phone, "password": pwd},
                timeout=20
            )
            data = resp.json()
            if resp.status_code == 200 and "job_id" in data:
                state["job_id"]     = data["job_id"]
                state["is_running"] = True
                append_log(f"✅ Job started! ID: {data['job_id']}", "#4ade80")
                set_status("RUNNING", "#4fa3ff")
                threading.Thread(target=poll_status, daemon=True).start()
            else:
                append_log(f"❌ Failed: {data.get('error', data)}", "#f87171")
                start_btn.disabled    = False
                progress_ring.visible = False
                set_status("IDLE", "#333355")
        except Exception as ex:
            append_log(f"❌ Network error: {ex}", "#f87171")
            start_btn.disabled    = False
            progress_ring.visible = False
            set_status("IDLE", "#333355")

        page.update()

    start_btn = ft.ElevatedButton(
        content=ft.Row(
            [ft.Icon(ft.icons.PLAY_ARROW_ROUNDED, color="white"),
             ft.Text("Start Automating", size=16, weight=ft.FontWeight.BOLD, color="white")],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=14),
            bgcolor={"": "#1e40af", "hovered": "#2563eb"},
            overlay_color="#3b82f620",
            elevation={"": 4, "hovered": 8},
            padding=ft.padding.symmetric(vertical=18),
        ),
        on_click=start_clicked,
        width=page.window_width,
    )

    automation_tab = ft.Container(
        padding=ft.padding.symmetric(horizontal=22, vertical=24),
        content=ft.Column(
            controls=[
                # Header
                ft.Row(
                    [ft.Icon(ft.icons.BOLT, color="#4fa3ff", size=28),
                     ft.Text("NNNRC Automator", size=24, weight=ft.FontWeight.BOLD, color="white")],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Text(
                    "Automated task completion bot",
                    size=13, color="#6677aa",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=16),
                # Card
                ft.Container(
                    content=ft.Column([phone_input, password_input], spacing=12),
                    bgcolor="#111122",
                    border_radius=16,
                    padding=20,
                    border=ft.border.all(1, "#222244"),
                ),
                ft.Container(height=12),
                start_btn,
                ft.Container(height=8),
                stats_row,
                ft.Divider(color="#222244", height=24),
                ft.Row([
                    ft.Icon(ft.icons.TERMINAL, color="#6677aa", size=16),
                    ft.Text("Execution Log", size=14,
                            weight=ft.FontWeight.W_600, color="#8899bb"),
                ]),
                ft.Container(
                    content=log_view,
                    bgcolor="#0a0a18",
                    border_radius=12,
                    padding=14,
                    border=ft.border.all(1, "#1a1a33"),
                    height=260,
                ),
            ],
            spacing=0,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        expand=True,
    )

    # ──────────────────────────────────────────────
    # TAB 2 — Live website WebView
    # ──────────────────────────────────────────────
    webview = ft.WebView(
        url="https://nnnrc.com/#/mytask",
        expand=True,
        on_page_started=lambda e: None,
    )

    website_tab = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.LANGUAGE, color="#4fa3ff", size=18),
                            ft.Text("nnnrc.com — Live View", size=14,
                                    weight=ft.FontWeight.W_600, color="white"),
                        ],
                        spacing=8,
                    ),
                    bgcolor="#111122",
                    padding=ft.padding.symmetric(horizontal=18, vertical=12),
                    border=ft.border.only(bottom=ft.BorderSide(1, "#222244")),
                ),
                webview,
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
    )

    # ──────────────────────────────────────────────
    # Tabs (compatible with Flet 0.21.2)
    # ──────────────────────────────────────────────
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=200,
        expand=True,
        tabs=[
            ft.Tab(
                text="🤖 Bot",
                content=automation_tab,
            ),
            ft.Tab(
                text="🌐 Live Site",
                content=website_tab,
            ),
        ],
        indicator_color="#4fa3ff",
        label_color="#4fa3ff",
        unselected_label_color="#6677aa",
    )

    page.add(tabs)


if __name__ == "__main__":
    ft.app(target=main)
