import os
import sys
import time
import queue
import threading
import tempfile
import subprocess
import webbrowser
from enum import Enum, auto
from datetime import datetime

from tkinter import (
    Tk, Frame, Label, Button, Entry, Text, Listbox, StringVar,
    messagebox, ttk, END, N, S, E, W,
    BOTH, LEFT, RIGHT, X, Y, VERTICAL, DISABLED, NORMAL, WORD
)


class STYLE(Enum):
    DEFAULT = auto()
    WARNING = auto()
    DANGER = auto()


class _StdoutTee:
    def __init__(self, original, log_queue):
        self._original = original
        self._queue = log_queue

    def write(self, text):
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        if text and text.strip():
            self._queue.put(text)

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass


class TGBotInterface:
    def __init__(self):
        self.ctx = {}
        self.root = None
        self.ON_KILL = None
        self._log_queue = queue.Queue()
        self._orig_stdout = None
        self._orig_stderr = None
        self._start_time = time.time()

    # -----------------------------------------------------------------
    # Wiring / lifecycle
    # -----------------------------------------------------------------
    def bind(self, **kwargs):
        self.ctx.update(kwargs)

    def start(self, onKill):
        self.ON_KILL = onKill
        self._orig_stdout, self._orig_stderr = sys.stdout, sys.stderr
        sys.stdout = _StdoutTee(self._orig_stdout, self._log_queue)
        sys.stderr = _StdoutTee(self._orig_stderr, self._log_queue)
        threading.Thread(target=self._start, daemon=True).start()

    def _start(self):
        self._build()
        self.root.mainloop()

    def close(self):
        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._orig_stderr:
            sys.stderr = self._orig_stderr
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
        if self.ON_KILL:
            self.ON_KILL()
        os._exit(0)

    def reload(self):
        python = sys.executable
        if self.root:
            self.root.destroy()
        os.execv(python, [python] + sys.argv)

    def run_async(self, fn, callback=None):
        """Runs fn() off the GUI thread; callback(result, error) fires back on the GUI thread."""
        def worker():
            try:
                result = fn()
                error = None
            except Exception as e:
                result = None
                error = e
            if self.root:
                self.root.after(0, lambda: callback(result, error) if callback else None)
        threading.Thread(target=worker, daemon=True).start()

    def _data(self):
        getter = self.ctx.get("get_data")
        return getter() if getter else {}

    def _push(self, *a, **kw):
        fn = self.ctx.get("push")
        if fn:
            fn(*a, **kw)

    def _notify(self, title, text, style=STYLE.DEFAULT):
        if style == STYLE.DANGER:
            messagebox.showerror(title, text)
        elif style == STYLE.WARNING:
            messagebox.showwarning(title, text)
        else:
            messagebox.showinfo(title, text)

    def _confirm(self, title, text):
        return messagebox.askyesno(title, text)

    def _build(self):
        self.root = Tk()
        self.root.title("🛠️ Dev Console")
        self.root.geometry("980x680")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=BOTH, expand=True, padx=6, pady=6)

        self._tab_dashboard = Frame(notebook)
        self._tab_sheet = Frame(notebook)
        self._tab_lessons = Frame(notebook)
        self._tab_siren = Frame(notebook)
        self._tab_users = Frame(notebook)
        self._tab_reminders = Frame(notebook)
        self._tab_admins = Frame(notebook)

        notebook.add(self._tab_dashboard, text="📊 Огляд")
        notebook.add(self._tab_sheet, text="📄 Таблиця")
        notebook.add(self._tab_lessons, text="✏️ Корекції")
        notebook.add(self._tab_siren, text="🚨 Сирена")
        notebook.add(self._tab_users, text="👥 Користувачі")
        notebook.add(self._tab_reminders, text="⏰ Нагадування")
        notebook.add(self._tab_admins, text="🔑 Доступи")

        self._build_dashboard(self._tab_dashboard)
        self._build_sheet_tab(self._tab_sheet)
        self._build_lessons_tab(self._tab_lessons)
        self._build_siren_tab(self._tab_siren)
        self._build_users_tab(self._tab_users)
        self._build_reminders_tab(self._tab_reminders)
        self._build_admins_tab(self._tab_admins)

        self.root.after(200, self._drain_log)
        self.root.after(1000, self._tick)

    def _build_dashboard(self, parent):
        info = Frame(parent)
        info.pack(fill=X, padx=8, pady=8)

        bot_name = self.ctx.get("bot_username") or "?"
        Label(info, text=f"🤖 Бот: @{bot_name}", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky=W, padx=4, pady=2)

        self._lbl_uptime = Label(info, text="⏱️ Час роботи: 00:00:00")
        self._lbl_uptime.grid(row=1, column=0, sticky=W, padx=4, pady=2)

        self._lbl_counts = Label(info, text="👥 0 | 👨‍👩‍👧 0 груп")
        self._lbl_counts.grid(row=2, column=0, sticky=W, padx=4, pady=2)

        self._dev_mode_var = StringVar(value="Dev Mode: ?")
        self._btn_dev_mode = Button(info, textvariable=self._dev_mode_var, command=self._toggle_dev_mode, width=22)
        self._btn_dev_mode.grid(row=0, column=1, rowspan=1, padx=10, pady=2, sticky=E)

        Button(info, text="🔄 Перезапустити процес", command=self._confirm_reload, width=22).grid(row=1, column=1, padx=10, pady=2, sticky=E)
        Button(info, text="❌ Закрити консоль/бота", command=self._confirm_close, width=22).grid(row=2, column=1, padx=10, pady=2, sticky=E)

        Label(parent, text="📜 Лог:", font=("Segoe UI", 10, "bold")).pack(anchor=W, padx=8)
        log_frame = Frame(parent)
        log_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        self._log_text = Text(log_frame, wrap=WORD, state=DISABLED, bg="#111", fg="#0f0", height=20)
        scroll = ttk.Scrollbar(log_frame, orient=VERTICAL, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scroll.set)
        self._log_text.pack(side=LEFT, fill=BOTH, expand=True)
        scroll.pack(side=RIGHT, fill=Y)

        self._refresh_dashboard()

    def _drain_log(self):
        drained = False
        while True:
            try:
                chunk = self._log_queue.get_nowait()
            except queue.Empty:
                break
            drained = True
            self._log_text.configure(state=NORMAL)
            self._log_text.insert(END, chunk)
            self._log_text.configure(state=DISABLED)
        if drained:
            self._log_text.see(END)
        self.root.after(200, self._drain_log)

    def _tick(self):
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self._lbl_uptime.configure(text=f"⏱️ Час роботи: {h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._tick)

    def _refresh_dashboard(self):
        d = self._data()
        users = d.get("users", {})
        groups = d.get("groups", [])
        self._lbl_counts.configure(text=f"👥 {len(users)} користувачів | 👨‍👩‍👧 {len(groups)} груп")
        dev_mode = bool(d.get("DEV_MODE"))
        self._dev_mode_var.set(f"Dev Mode: {'ON 🟥' if dev_mode else 'OFF 🟩'}")

    def _toggle_dev_mode(self):
        d = self._data()
        d["DEV_MODE"] = not bool(d.get("DEV_MODE"))
        self._push()
        self._refresh_dashboard()

    def _confirm_reload(self):
        if self._confirm("Перезапуск", "Перезапустити процес бота зараз?"):
            self.reload()

    def _confirm_close(self):
        if self._confirm("Вихід", "Закрити консоль і зупинити бота повністю?"):
            self.close()

    # -----------------------------------------------------------------
    # Sheet tab
    # -----------------------------------------------------------------
    def _build_sheet_tab(self, parent):
        d = self._data()
        sheet_url = d.get("bot_data", {}).get("sheet", "")

        top = Frame(parent)
        top.pack(fill=X, padx=8, pady=8)
        Label(top, text="🔗 Джерело:").pack(side=LEFT)
        Label(top, text=sheet_url, fg="#0645AD").pack(side=LEFT, padx=4)
        Button(top, text="Відкрити", command=lambda: webbrowser.open(sheet_url) if sheet_url else None).pack(side=LEFT, padx=6)

        actions = Frame(parent)
        actions.pack(fill=X, padx=8, pady=4)
        self._sheet_status = Label(actions, text="Статус: -")
        self._sheet_status.pack(side=LEFT)
        Button(actions, text="🔄 Оновити розклад з таблиці", command=self._do_reload_schedule).pack(side=RIGHT, padx=4)
        Button(actions, text="Оновити список уроків", command=self._refresh_lessons_tree).pack(side=RIGHT, padx=4)

        Label(parent, text="Уроки (ID / Назва / Код посилання):", font=("Segoe UI", 10, "bold")).pack(anchor=W, padx=8, pady=(8, 0))
        cols = ("id", "name", "code")
        self._lessons_tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
        for c, txt, w in [("id", "ID", 50), ("name", "Назва", 260), ("code", "Код посилання", 300)]:
            self._lessons_tree.heading(c, text=txt)
            self._lessons_tree.column(c, width=w, anchor=W)
        self._lessons_tree.pack(fill=BOTH, expand=True, padx=8, pady=8)

        self._refresh_lessons_tree()

    def _refresh_lessons_tree(self):
        db = self.ctx.get("database")
        if not db:
            return
        for row in self._lessons_tree.get_children():
            self._lessons_tree.delete(row)
        for lid, name in db.lessons_names.items():
            code = db.lessons_ids.get(lid, "")
            self._lessons_tree.insert("", END, values=(lid, name or "", code or ""))

    def _do_reload_schedule(self):
        fn = self.ctx.get("reload_schedule")
        if not fn:
            self._notify("Недоступно", "reload_schedule не підключено", STYLE.WARNING)
            return
        self._sheet_status.configure(text="Статус: оновлення...")

        def done(result, error):
            if error:
                self._sheet_status.configure(text=f"Статус: помилка ({error})")
                self._notify("Помилка", f"Не вдалося оновити таблицю:\n{error}", STYLE.DANGER)
            else:
                self._sheet_status.configure(text=f"Статус: оновлено о {datetime.now().strftime('%H:%M:%S')}")
                self._refresh_lessons_tree()
                self._refresh_lesson_choice()

        self.run_async(fn, done)

    def _refresh_lesson_choice(self):
        db = self.ctx.get("database")
        if hasattr(self, "_lesson_choice") and db:
            values = ["-1 - Видалити"] + [f"{lid} - {name}" for lid, name in db.lessons_names.items()]
            self._lesson_choice["values"] = values

    def _build_lessons_tab(self, parent):
        top = Frame(parent)
        top.pack(fill=X, padx=8, pady=8)
        Button(top, text="🔄 Оновити", command=self._refresh_corrections_tree).pack(side=LEFT)
        Button(top, text="🗑️ Видалити виділене", command=self._delete_selected_correction).pack(side=LEFT, padx=6)
        Button(top, text="🧹 Очистити застарілі", command=self._clear_old_corrections).pack(side=LEFT, padx=6)

        cols = ("day", "time", "value")
        self._corr_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c, txt, w in [("day", "День", 60), ("time", "Час", 80), ("value", "Дія", 400)]:
            self._corr_tree.heading(c, text=txt)
            self._corr_tree.column(c, width=w, anchor=W)
        self._corr_tree.pack(fill=BOTH, expand=True, padx=8, pady=4)

        form = ttk.LabelFrame(parent, text="Додати / змінити корекцію")
        form.pack(fill=X, padx=8, pady=8)

        Label(form, text="День (число):").grid(row=0, column=0, padx=4, pady=4, sticky=W)
        self._corr_day = Entry(form, width=8)
        self._corr_day.grid(row=0, column=1, padx=4, pady=4)

        Label(form, text="Час (HH:MM):").grid(row=0, column=2, padx=4, pady=4, sticky=W)
        self._corr_time = Entry(form, width=8)
        self._corr_time.grid(row=0, column=3, padx=4, pady=4)

        Label(form, text="Урок:").grid(row=0, column=4, padx=4, pady=4, sticky=W)
        db = self.ctx.get("database")
        values = ["-1 - Видалити"]
        if db:
            values += [f"{lid} - {name}" for lid, name in db.lessons_names.items()]
        self._lesson_choice = ttk.Combobox(form, values=values, width=30, state="readonly")
        if values:
            self._lesson_choice.current(0)
        self._lesson_choice.grid(row=0, column=5, padx=4, pady=4)

        Button(form, text="✅ Застосувати", command=self._apply_correction).grid(row=0, column=6, padx=8, pady=4)

        self._refresh_corrections_tree()

    def _refresh_corrections_tree(self):
        rs = self.ctx.get("rescheduler")
        db = self.ctx.get("database")
        for row in self._corr_tree.get_children():
            self._corr_tree.delete(row)
        if not rs:
            return
        for day, times in rs.data.items():
            for t, lesson_id in times.items():
                if str(lesson_id) == "-1":
                    label = "❌ Видалено"
                else:
                    name = db.lessons_names.get(int(lesson_id)) if db else None
                    label = f"🔄 → {name or lesson_id}"
                self._corr_tree.insert("", END, values=(day, t, label))

    def _delete_selected_correction(self):
        rs = self.ctx.get("rescheduler")
        sel = self._corr_tree.selection()
        if not rs or not sel:
            return
        for item in sel:
            day, t, _ = self._corr_tree.item(item, "values")
            rs.clearLesson(int(day), t)
        self._refresh_corrections_tree()

    def _clear_old_corrections(self):
        rs = self.ctx.get("rescheduler")
        if not rs:
            return
        today = datetime.now().day
        rs.clearOld(today)
        self._refresh_corrections_tree()
        self._notify("Готово", f"Видалено корекції старіші за день {today}")

    def _apply_correction(self):
        rs = self.ctx.get("rescheduler")
        db = self.ctx.get("database")
        if not rs or not db:
            self._notify("Недоступно", "rescheduler/database не підключено", STYLE.WARNING)
            return
        try:
            day = int(self._corr_day.get().strip())
        except ValueError:
            self._notify("Помилка", "День має бути числом", STYLE.WARNING)
            return
        time_val = self._corr_time.get().strip()
        if not time_val or ":" not in time_val:
            self._notify("Помилка", "Час має бути у форматі HH:MM", STYLE.WARNING)
            return
        choice = self._lesson_choice.get()
        lesson_id = choice.split(" - ")[0].strip() if choice else "-1"

        try:
            target_date = datetime.now().replace(day=day)
            from .lessons import getWeek
            raw_day = db.getSchedule(getWeek(target_date), target_date, False)
            is_original = time_val in raw_day
        except Exception:
            is_original = False

        rs.schedule(day, time_val, lesson_id, is_original)
        self._refresh_corrections_tree()
        self._notify("Готово", f"Корекція на день {day} о {time_val} застосована")

    def _build_siren_tab(self, parent):
        d = self._data()
        city = d.get("bot_data", {}).get("citySiren", "")

        top = Frame(parent)
        top.pack(fill=X, padx=8, pady=8)
        Label(top, text="📍 Місто/район моніторингу:").pack(side=LEFT)
        self._siren_city = Entry(top, width=30)
        self._siren_city.insert(0, city)
        self._siren_city.pack(side=LEFT, padx=6)
        Button(top, text="💾 Зберегти", command=self._save_siren_city).pack(side=LEFT, padx=4)

        status = Frame(parent)
        status.pack(fill=X, padx=8, pady=8)
        self._siren_status_lbl = Label(status, text="Статус: невідомо", font=("Segoe UI", 12, "bold"))
        self._siren_status_lbl.pack(side=LEFT)
        Button(status, text="🔍 Перевірити зараз", command=self._check_siren_now).pack(side=RIGHT, padx=4)
        Button(status, text="🗺️ Показати карту", command=self._show_siren_map).pack(side=RIGHT, padx=4)

        preview = ttk.LabelFrame(parent, text="Прев'ю тривожного сповіщення (не надсилається користувачам)")
        preview.pack(fill=X, padx=8, pady=8)
        self._siren_preview = Text(preview, height=6, wrap=WORD)
        self._siren_preview.pack(fill=X, padx=6, pady=6)
        Button(preview, text="Згенерувати прев'ю", command=self._build_siren_preview).pack(anchor=E, padx=6, pady=(0, 6))

        test_frame = ttk.LabelFrame(parent, text="Тестове сповіщення лише для розробників (data.devs)")
        test_frame.pack(fill=X, padx=8, pady=8)
        Button(test_frame, text="📨 Надіслати тест розробникам", command=self._send_siren_test_to_devs).pack(padx=6, pady=6)

        self._check_siren_now()

    def _save_siren_city(self):
        d = self._data()
        d.setdefault("bot_data", {})["citySiren"] = self._siren_city.get().strip()
        self._push()
        siren = self.ctx.get("siren")
        if siren:
            siren.City = self._siren_city.get().strip()
            siren._alert_data = None
        self._notify("Збережено", "Місто моніторингу оновлено")

    def _check_siren_now(self):
        siren = self.ctx.get("siren")
        if not siren:
            self._siren_status_lbl.configure(text="Статус: siren не підключено")
            return
        self._siren_status_lbl.configure(text="Статус: перевірка...")

        def done(result, error):
            if error:
                self._siren_status_lbl.configure(text=f"Статус: помилка ({error})")
                return
            if result:
                self._siren_status_lbl.configure(text="🟥 Є тривога", fg="red")
            else:
                self._siren_status_lbl.configure(text="🟩 Немає тривоги", fg="green")

        self.run_async(siren.cityTake, done)

    def _show_siren_map(self):
        siren = self.ctx.get("siren")
        if not siren:
            self._notify("Недоступно", "siren не підключено", STYLE.WARNING)
            return

        def fetch():
            return siren.getMap().read()

        def done(result, error):
            if error or not result:
                self._notify("Помилка", f"Не вдалося завантажити карту:\n{error}", STYLE.DANGER)
                return
            path = os.path.join(tempfile.gettempdir(), "siren_map.png")
            with open(path, "wb") as f:
                f.write(result)
            self._open_file(path)

        self.run_async(fetch, done)

    def _open_file(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self._notify("Помилка", f"Не вдалося відкрити файл:\n{e}", STYLE.DANGER)

    def _build_siren_preview(self):
        siren = self.ctx.get("siren")
        if not siren:
            return

        def check():
            return siren.cityTake()

        def done(result, error):
            if error:
                self._notify("Помилка", str(error), STYLE.DANGER)
                return
            text = (
                "═🟥════════🟥\n"
                "!Повітряна тривоги!\n"
                "═🟥════════🟥"
                if result else
                "═🟩════════🟩\n"
                "!Відбій тривоги!\n"
                "═🟩════════🟩"
            )
            self._siren_preview.delete("1.0", END)
            self._siren_preview.insert(END, text)

        self.run_async(check, done)

    def _send_siren_test_to_devs(self):
        bot = self.ctx.get("bot")
        d = self._data()
        devs = d.get("devs", [])
        if not bot or not devs:
            self._notify("Недоступно", "bot/devs не підключено або список порожній", STYLE.WARNING)
            return
        if not self._confirm("Підтвердження", f"Надіслати тестове сповіщення {len(devs)} розробникам?"):
            return
        text = self._siren_preview.get("1.0", END).strip() or "Тестове сповіщення сирени"

        def send():
            failed = []
            for dev_id in devs:
                try:
                    bot.send_message(dev_id, f"🧪 [ТЕСТ]\n{text}", parse_mode="HTML")
                except Exception as e:
                    failed.append((dev_id, str(e)))
            return failed

        def done(result, error):
            if error:
                self._notify("Помилка", str(error), STYLE.DANGER)
            elif result:
                self._notify("Частково надіслано", f"Не вдалося надіслати: {result}", STYLE.WARNING)
            else:
                self._notify("Готово", "Тестове сповіщення надіслано")

        self.run_async(send, done)

    def _build_users_tab(self, parent):
        left = Frame(parent)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=8, pady=8)
        right = Frame(parent)
        right.pack(side=RIGHT, fill=BOTH, expand=True, padx=8, pady=8)

        Label(left, text="👥 Користувачі", font=("Segoe UI", 10, "bold")).pack(anchor=W)
        cols = ("id", "name", "account")
        self._users_tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
        for c, txt, w in [("id", "Chat ID", 120), ("name", "Ім'я", 140), ("account", "Акаунт", 60)]:
            self._users_tree.heading(c, text=txt)
            self._users_tree.column(c, width=w, anchor=W)
        self._users_tree.pack(fill=BOTH, expand=True)
        Button(left, text="🔄 Оновити", command=self._refresh_users_tree).pack(anchor=W, pady=4)
        Button(left, text="🗑️ Відписати виділеного", command=self._remove_selected_user).pack(anchor=W)

        Label(right, text="👨‍👩‍👧 Групи", font=("Segoe UI", 10, "bold")).pack(anchor=W)
        self._groups_list = Listbox(right, height=10)
        self._groups_list.pack(fill=X)
        Button(right, text="🔄 Оновити", command=self._refresh_groups_list).pack(anchor=W, pady=4)
        Button(right, text="🗑️ Прибрати виділену групу", command=self._remove_selected_group).pack(anchor=W)

        broadcast = ttk.LabelFrame(right, text="📢 Розсилка всім (users + groups)")
        broadcast.pack(fill=BOTH, expand=True, pady=(16, 0))
        self._broadcast_text = Text(broadcast, height=6, wrap=WORD)
        self._broadcast_text.pack(fill=BOTH, expand=True, padx=6, pady=6)
        Button(broadcast, text="📨 Надіслати", command=self._do_broadcast).pack(anchor=E, padx=6, pady=(0, 6))

        self._refresh_users_tree()
        self._refresh_groups_list()

    def _refresh_users_tree(self):
        d = self._data()
        for row in self._users_tree.get_children():
            self._users_tree.delete(row)
        for uid, info in d.get("users", {}).items():
            self._users_tree.insert("", END, values=(uid, info.get("name", ""), info.get("account", 0)))

    def _refresh_groups_list(self):
        d = self._data()
        self._groups_list.delete(0, END)
        for gid in d.get("groups", []):
            self._groups_list.insert(END, gid)

    def _remove_selected_user(self):
        sel = self._users_tree.selection()
        if not sel:
            return
        d = self._data()
        for item in sel:
            uid, name, _ = self._users_tree.item(item, "values")
            if self._confirm("Підтвердження", f"Відписати {name} ({uid})?"):
                d.get("users", {}).pop(str(uid), None)
        self._push()
        self._refresh_users_tree()
        self._refresh_dashboard()

    def _remove_selected_group(self):
        sel = self._groups_list.curselection()
        if not sel:
            return
        gid = self._groups_list.get(sel[0])
        if self._confirm("Підтвердження", f"Прибрати групу {gid}?"):
            d = self._data()
            if gid in d.get("groups", []):
                d["groups"].remove(gid)
                self._push()
        self._refresh_groups_list()
        self._refresh_dashboard()

    def _do_broadcast(self):
        bot = self.ctx.get("bot")
        text = self._broadcast_text.get("1.0", END).strip()
        if not bot or not text:
            return
        d = self._data()
        targets = list(d.get("users", {}).keys()) + list(d.get("groups", []))
        if not self._confirm("Підтвердження", f"Надіслати повідомлення {len(targets)} чатам?"):
            return

        def send():
            sent, failed = 0, 0
            for chat_id in targets:
                try:
                    bot.send_message(int(chat_id), f"📢 <b>Оголошення:</b>\n\n{text}", parse_mode="HTML")
                    sent += 1
                except Exception:
                    failed += 1
            return sent, failed

        def done(result, error):
            if error:
                self._notify("Помилка", str(error), STYLE.DANGER)
            else:
                sent, failed = result
                self._notify("Готово", f"Відправлено: {sent}\nНе доставлено: {failed}")

        self.run_async(send, done)

    def _build_reminders_tab(self, parent):
        top = Frame(parent)
        top.pack(fill=X, padx=8, pady=8)
        Button(top, text="🔄 Оновити", command=self._refresh_reminders_tree).pack(side=LEFT)
        Button(top, text="🗑️ Видалити виділене", command=self._delete_selected_reminder).pack(side=LEFT, padx=6)

        cols = ("time", "text", "exclude")
        self._reminders_tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for c, txt, w in [("time", "Час", 70), ("text", "Текст", 380), ("exclude", "Виключення", 150)]:
            self._reminders_tree.heading(c, text=txt)
            self._reminders_tree.column(c, width=w, anchor=W)
        self._reminders_tree.pack(fill=BOTH, expand=True, padx=8, pady=4)

        form = ttk.LabelFrame(parent, text="Додати / оновити нагадування")
        form.pack(fill=X, padx=8, pady=8)
        Label(form, text="Час (HH:MM):").grid(row=0, column=0, padx=4, pady=4, sticky=W)
        self._rem_time = Entry(form, width=10)
        self._rem_time.grid(row=0, column=1, padx=4, pady=4)
        Label(form, text="Текст:").grid(row=0, column=2, padx=4, pady=4, sticky=W)
        self._rem_text = Entry(form, width=40)
        self._rem_text.grid(row=0, column=3, padx=4, pady=4)
        Label(form, text="Виключити дні (через кому, напр. СБ,ВС):").grid(row=1, column=0, columnspan=2, padx=4, pady=4, sticky=W)
        self._rem_exclude = Entry(form, width=20)
        self._rem_exclude.grid(row=1, column=2, padx=4, pady=4, sticky=W)
        Button(form, text="✅ Зберегти", command=self._save_reminder).grid(row=1, column=3, padx=4, pady=4, sticky=E)

        self._refresh_reminders_tree()

    def _refresh_reminders_tree(self):
        d = self._data()
        for row in self._reminders_tree.get_children():
            self._reminders_tree.delete(row)
        for t, r in d.get("bot_data", {}).get("reminders", {}).items():
            self._reminders_tree.insert("", END, values=(t, r.get("text", ""), ",".join(r.get("exclude", []))))

    def _delete_selected_reminder(self):
        sel = self._reminders_tree.selection()
        if not sel:
            return
        d = self._data()
        reminders = d.get("bot_data", {}).get("reminders", {})
        for item in sel:
            t, _, _ = self._reminders_tree.item(item, "values")
            reminders.pop(t, None)
        self._push()
        self._refresh_reminders_tree()

    def _save_reminder(self):
        t = self._rem_time.get().strip()
        text = self._rem_text.get().strip()
        if not t or ":" not in t or not text:
            self._notify("Помилка", "Заповніть час (HH:MM) та текст", STYLE.WARNING)
            return
        exclude = [x.strip() for x in self._rem_exclude.get().split(",") if x.strip()]
        d = self._data()
        d.setdefault("bot_data", {}).setdefault("reminders", {})[t] = {"exclude": exclude, "text": text}
        self._push()
        self._refresh_reminders_tree()
        self._notify("Готово", f"Нагадування на {t} збережено")

    def _build_admins_tab(self, parent):
        admins_frame = ttk.LabelFrame(parent, text="🔑 Адміни")
        admins_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self._admins_list = Listbox(admins_frame, height=10)
        self._admins_list.pack(side=LEFT, fill=BOTH, expand=True, padx=6, pady=6)
        a_btns = Frame(admins_frame)
        a_btns.pack(side=RIGHT, fill=Y, padx=6, pady=6)
        self._admin_entry = Entry(a_btns, width=16)
        self._admin_entry.pack(pady=(0, 4))
        Button(a_btns, text="➕ Додати", command=self._add_admin).pack(fill=X, pady=2)
        Button(a_btns, text="➖ Видалити виділене", command=self._remove_admin).pack(fill=X, pady=2)

        devs_frame = ttk.LabelFrame(parent, text="🛠️ Розробники")
        devs_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self._devs_list = Listbox(devs_frame, height=10)
        self._devs_list.pack(side=LEFT, fill=BOTH, expand=True, padx=6, pady=6)
        d_btns = Frame(devs_frame)
        d_btns.pack(side=RIGHT, fill=Y, padx=6, pady=6)
        self._dev_entry = Entry(d_btns, width=16)
        self._dev_entry.pack(pady=(0, 4))
        Button(d_btns, text="➕ Додати", command=self._add_dev).pack(fill=X, pady=2)
        Button(d_btns, text="➖ Видалити виділене", command=self._remove_dev).pack(fill=X, pady=2)

        self._refresh_admins_devs()

    def _refresh_admins_devs(self):
        d = self._data()
        self._admins_list.delete(0, END)
        for uid in d.get("admins", []):
            self._admins_list.insert(END, uid)
        self._devs_list.delete(0, END)
        for uid in d.get("devs", []):
            self._devs_list.insert(END, uid)

    def _add_admin(self):
        try:
            uid = int(self._admin_entry.get().strip())
        except ValueError:
            self._notify("Помилка", "ID має бути числом", STYLE.WARNING)
            return
        d = self._data()
        if uid not in d.setdefault("admins", []):
            d["admins"].append(uid)
            self._push()
        self._refresh_admins_devs()

    def _remove_admin(self):
        sel = self._admins_list.curselection()
        if not sel:
            return
        uid = self._admins_list.get(sel[0])
        d = self._data()
        if uid in d.get("admins", []):
            d["admins"].remove(uid)
            self._push()
        self._refresh_admins_devs()

    def _add_dev(self):
        try:
            uid = int(self._dev_entry.get().strip())
        except ValueError:
            self._notify("Помилка", "ID має бути числом", STYLE.WARNING)
            return
        d = self._data()
        if uid not in d.setdefault("devs", []):
            d["devs"].append(uid)
            self._push()
        self._refresh_admins_devs()

    def _remove_dev(self):
        sel = self._devs_list.curselection()
        if not sel:
            return
        uid = self._devs_list.get(sel[0])
        d = self._data()
        if uid in d.get("devs", []):
            d["devs"].remove(uid)
            self._push()
        self._refresh_admins_devs()