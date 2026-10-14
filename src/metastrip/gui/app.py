"""Metadata Stripper desktop app."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from metastrip import __version__
from metastrip.core import (
    FileMetadata,
    MetaStripError,
    Risk,
    StripOptions,
    StripResult,
    collect_files,
    inspect_file,
    strip_file,
    strip_many,
    suggested_ids,
)
from metastrip.core import report as report_mod
from metastrip.core.handlers import SUPPORTED_EXTENSIONS

_VALUE_WIDTH = 120
_MODES = {"Remove everything": "all", "Suggested (High + Medium risk)": "suggested"}
_RISK_COLORS = {
    "dark": {"high": "#ff6b6b", "medium": "#ffa94d", "low": "#9aa0a6"},
    "light": {"high": "#c92a2a", "medium": "#d9480f", "low": "#5f6368"},
}


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        self.title("Metadata Stripper")
        self.geometry("1150x700")
        self.minsize(900, 540)

        self._files: list[Path] = []
        self._metas: dict[Path, FileMetadata] = {}
        self._current: Path | None = None
        self._selected: set[str] = set()
        self._sort_column = "risk"
        self._sort_reverse = True
        self._events: queue.Queue = queue.Queue()
        self._busy = False

        self.in_place = tk.BooleanVar(value=False)
        self.keep_orientation = tk.BooleanVar(value=True)

        self._build_layout()
        self._style_trees()
        self._set_status("Add images or a folder to get started.")

    # ------------------------------------------------------------ layout --
    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 6))
        ctk.CTkButton(bar, text="Add Files", width=100, command=self._add_files).pack(side="left")
        ctk.CTkButton(bar, text="Add Folder", width=100, command=self._add_folder).pack(side="left", padx=6)
        ctk.CTkButton(
            bar, text="Clear", width=70, fg_color="gray40", hover_color="gray30", command=self._clear
        ).pack(side="left")
        ctk.CTkLabel(bar, text=f"v{__version__}", text_color="gray").pack(side="right", padx=(10, 0))
        theme = ctk.CTkOptionMenu(bar, values=["System", "Dark", "Light"], width=100, command=self._set_theme)
        theme.pack(side="right")

        left = ctk.CTkFrame(self, width=280)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Files", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(8, 4)
        )
        self.file_tree = ttk.Treeview(left, columns=("risk",), show="tree", selectmode="browse", height=10)
        self.file_tree.column("#0", width=200)
        self.file_tree.column("risk", width=60, anchor="center")
        self.file_tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.file_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(0, 4))
        self.file_tree.configure(yscrollcommand=scroll.set)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        self.summary = ctk.CTkLabel(top, text="No file selected", anchor="w")
        self.summary.pack(side="left")
        self.filter_entry = ctk.CTkEntry(top, placeholder_text="Filter tags...", width=220)
        self.filter_entry.pack(side="right")
        self.filter_entry.bind("<KeyRelease>", lambda _e: self._refresh_tree())

        columns = ("risk", "group", "name", "value")
        self.tree = ttk.Treeview(right, columns=columns, show="headings", selectmode="extended")
        for col, label, width in (
            ("risk", "Risk", 70),
            ("group", "Group", 100),
            ("name", "Tag", 200),
            ("value", "Value", 420),
        ):
            self.tree.heading(col, text=label, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, anchor="w", stretch=(col == "value"))
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        vscroll = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        vscroll.grid(row=1, column=1, sticky="ns", pady=(0, 8), padx=(0, 4))
        self.tree.configure(yscrollcommand=vscroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tag_select)

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(0, 8))
        self.action_buttons = [
            ctk.CTkButton(actions, text="Select Suggested", width=130, command=self._select_suggested),
            ctk.CTkButton(actions, text="Select All", width=90, command=self._select_all),
            ctk.CTkButton(actions, text="Remove Selected", width=130, command=self._remove_selected),
            ctk.CTkButton(actions, text="Strip All Tags", width=110, command=self._strip_current),
            ctk.CTkButton(
                actions,
                text="Export Report",
                width=110,
                fg_color="gray40",
                hover_color="gray30",
                command=self._export_report,
            ),
        ]
        for button in self.action_buttons:
            button.pack(side="left", padx=(0, 6))

        bottom = ctk.CTkFrame(self)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(6, 6))
        ctk.CTkCheckBox(bottom, text="Edit originals in place (backup kept)", variable=self.in_place).pack(
            side="left", padx=10, pady=10
        )
        ctk.CTkCheckBox(bottom, text="Keep rotation", variable=self.keep_orientation).pack(
            side="left", padx=10
        )
        self.batch_button = ctk.CTkButton(bottom, text="Clean All Files", width=130, command=self._clean_all)
        self.batch_button.pack(side="right", padx=10)
        self.mode_menu = ctk.CTkOptionMenu(bottom, values=list(_MODES), width=230)
        self.mode_menu.pack(side="right")

        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12)
        self.status = ctk.CTkLabel(self, text="", anchor="w")
        self.status.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 10))

    # ------------------------------------------------------------ styling --
    def _set_theme(self, mode: str) -> None:
        ctk.set_appearance_mode(mode.lower())
        self._style_trees()

    def _style_trees(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        bg, fg, head = ("#2b2b2b", "#e6e6e6", "#3a3a3a") if dark else ("#ffffff", "#1f1f1f", "#e8e8e8")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview", background=bg, fieldbackground=bg, foreground=fg, borderwidth=0, rowheight=26
        )
        style.configure("Treeview.Heading", background=head, foreground=fg, relief="flat")
        style.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "#ffffff")])
        colors = _RISK_COLORS["dark" if dark else "light"]
        for name, color in colors.items():
            self.tree.tag_configure(name, foreground=color)
            self.file_tree.tag_configure(name, foreground=color)

    # -------------------------------------------------------------- files --
    def _add_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        chosen = filedialog.askopenfilenames(
            title="Choose images", filetypes=[("Images", patterns), ("All files", "*.*")]
        )
        self._add_paths([Path(p) for p in chosen])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Choose a folder")
        if folder:
            self._add_paths([Path(folder)], recursive=True)

    def _add_paths(self, paths: list[Path], recursive: bool = False) -> None:
        if not paths:
            return
        try:
            found = collect_files(paths, recursive=recursive)
        except MetaStripError as exc:
            messagebox.showerror("Cannot add", str(exc))
            return
        new = [p for p in found if p not in self._files]
        for path in new:
            self._files.append(path)
            self.file_tree.insert("", "end", iid=str(path), text=path.name, values=("",))
        if new and self._current is None:
            self.file_tree.selection_set(str(new[0]))
        self._set_status(f"{len(new)} file(s) added, {len(self._files)} total.")

    def _clear(self) -> None:
        if self._busy:
            return
        self._files.clear()
        self._metas.clear()
        self._current = None
        self._selected.clear()
        self.file_tree.delete(*self.file_tree.get_children())
        self._refresh_tree()
        self.summary.configure(text="No file selected")
        self.progress.set(0)
        self._set_status("Cleared.")

    def _on_file_select(self, _event=None) -> None:
        selection = self.file_tree.selection()
        if not selection:
            return
        self._load_file(Path(selection[0]))

    def _load_file(self, path: Path, force: bool = False) -> None:
        self._current = path
        self._selected.clear()
        if force or path not in self._metas:
            try:
                self._metas[path] = inspect_file(path)
            except MetaStripError as exc:
                self._metas.pop(path, None)
                self.summary.configure(text=f"{path.name}: cannot read")
                self._refresh_tree()
                self._set_status(f"Error: {exc}")
                return
        meta = self._metas[path]
        highest = meta.highest_risk
        self.file_tree.item(
            str(path),
            values=(highest.label if highest else "None",),
            tags=(highest.label.lower(),) if highest else (),
        )
        counts = meta.counts()
        self.summary.configure(
            text=f"{path.name}  |  {meta.format}  |  {len(meta.entries)} items  "
            f"({counts[Risk.HIGH]} high, {counts[Risk.MEDIUM]} medium, {counts[Risk.LOW]} low)"
        )
        self._refresh_tree()

    # -------------------------------------------------------- tags table --
    def _visible_entries(self):
        meta = self._metas.get(self._current) if self._current else None
        if not meta:
            return []
        query = self.filter_entry.get().strip().lower()
        entries = [e for e in meta.entries if not query or query in f"{e.group} {e.name} {e.value}".lower()]
        keys = {
            "risk": lambda e: (e.risk, e.name),
            "group": lambda e: (e.group, e.name),
            "name": lambda e: e.name.lower(),
            "value": lambda e: e.value.lower(),
        }
        return sorted(entries, key=keys[self._sort_column], reverse=self._sort_reverse)

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for entry in self._visible_entries():
            value = (
                entry.value if len(entry.value) <= _VALUE_WIDTH else entry.value[: _VALUE_WIDTH - 3] + "..."
            )
            self.tree.insert(
                "",
                "end",
                iid=entry.id,
                values=(entry.risk.label, entry.group, entry.name, value),
                tags=(entry.risk.label.lower(),),
            )
        present = [i for i in self._selected if self.tree.exists(i)]
        if present:
            self.tree.selection_set(present)

    def _sort_by(self, column: str) -> None:
        self._sort_reverse = not self._sort_reverse if column == self._sort_column else column == "risk"
        self._sort_column = column
        self._refresh_tree()

    def _on_tag_select(self, _event=None) -> None:
        visible = set(self.tree.get_children())
        chosen = set(self.tree.selection())
        self._selected = (self._selected - visible) | chosen

    def _select_suggested(self) -> None:
        meta = self._current_meta()
        if meta:
            self._selected = set(suggested_ids(meta))
            self._refresh_tree()
            self._set_status(f"{len(self._selected)} suggested item(s) selected.")

    def _select_all(self) -> None:
        meta = self._current_meta()
        if meta:
            self._selected = {e.id for e in meta.entries}
            self._refresh_tree()

    def _current_meta(self) -> FileMetadata | None:
        meta = self._metas.get(self._current) if self._current else None
        if not meta:
            self._set_status("Select a readable file first.")
        return meta

    # ----------------------------------------------------------- actions --
    def _strip_options(self, **overrides) -> StripOptions:
        base = {"in_place": self.in_place.get(), "keep_orientation": self.keep_orientation.get()}
        base.update(overrides)
        return StripOptions(**base)

    def _remove_selected(self) -> None:
        if not self._selected:
            self._set_status("Nothing selected.")
            return
        self._run_single(self._strip_options(mode="selected", remove_ids=frozenset(self._selected)))

    def _strip_current(self) -> None:
        self._run_single(self._strip_options(mode="all"))

    def _run_single(self, options: StripOptions) -> None:
        if not self._current or self._busy:
            return
        try:
            result = strip_file(self._current, options)
        except MetaStripError as exc:
            messagebox.showerror("Could not clean file", str(exc))
            return
        self._set_status(self._describe(result))
        if result.output and options.in_place:
            self._load_file(self._current, force=True)

    @staticmethod
    def _describe(result: StripResult) -> str:
        if not result.ok:
            return f"Error: {result.source.name}: {result.error}"
        if result.skipped:
            return f"{result.source.name}: skipped ({result.reason})"
        note = f", backup {result.backup.name}" if result.backup else ""
        return f"Saved {result.output.name} (removed {len(result.removed)} items{note})"

    def _clean_all(self) -> None:
        if self._busy or not self._files:
            self._set_status("Add files first.")
            return
        mode = _MODES[self.mode_menu.get()]
        if self.in_place.get() and not messagebox.askyesno(
            "Edit originals?", "Originals will be modified (a .bak backup is made for each). Continue?"
        ):
            return
        options = self._strip_options(mode=mode)
        files = list(self._files)
        self._busy = True
        self.batch_button.configure(state="disabled")
        self.progress.set(0)

        def work() -> None:
            results = strip_many(
                files, options, on_progress=lambda i, n, r: self._events.put(("progress", i, n, r))
            )
            self._events.put(("done", results))

        threading.Thread(target=work, daemon=True).start()
        self.after(60, self._poll_events)

    def _poll_events(self) -> None:
        finished = False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                _, done, total, result = event
                self.progress.set(done / total)
                self._set_status(f"({done}/{total}) {self._describe(result)}")
            else:
                self._finish_batch(event[1])
                finished = True
        if not finished:
            self.after(60, self._poll_events)

    def _finish_batch(self, results: list[StripResult]) -> None:
        self._busy = False
        self.batch_button.configure(state="normal")
        cleaned = sum(1 for r in results if r.ok and not r.skipped)
        failed = [r for r in results if not r.ok]
        self._set_status(
            f"Done: {cleaned} cleaned, {len(results) - cleaned - len(failed)} skipped, {len(failed)} failed."
        )
        if self.in_place.get():
            self._metas.clear()
            if self._current:
                self._load_file(self._current, force=True)
        if failed:
            lines = "\n".join(f"{r.source.name}: {r.error}" for r in failed[:10])
            messagebox.showwarning("Some files failed", lines)

    def _export_report(self) -> None:
        if not self._files:
            self._set_status("Add files first.")
            return
        target = filedialog.asksaveasfilename(
            title="Save report", defaultextension=".json", filetypes=[("JSON", "*.json"), ("CSV", "*.csv")]
        )
        if not target:
            return
        metas = []
        for path in self._files:
            try:
                metas.append(self._metas.get(path) or inspect_file(path))
            except MetaStripError:
                continue
        text = report_mod.to_csv(metas) if target.lower().endswith(".csv") else report_mod.to_json(metas)
        try:
            Path(target).write_text(text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Could not save report", str(exc))
            return
        self._set_status(f"Report saved to {target}")

    def _set_status(self, text: str) -> None:
        self.status.configure(text=text)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
