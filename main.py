"""
ai_container.py – PySide6 GUI for the smolagents multi-agent team
(local Ollama, no cloud keys).

Modules:
    paths.py         — shared, CWD-independent paths
    batfish.py       — Batfish client + network tools
    tools_files.py   — upload file tools (list_uploads, file_reader)
    tools_docker.py  — Dockerfile/compose generation, up/logs/down, endpoint test
    tools_db.py      — schema + read-only SQL tools
    agents.py        — the four agents
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from theme import DARK_THEME
from agents import (
    DEFAULT_MODEL_ID,
    list_ollama_models,
    manager_agent,
    set_model_for_all_agents,
)
from paths import APP_DIR, UPLOADS_DIR
from tools_files import read_document

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
    QComboBox
)

# ──────────────────────────────────────────────
# 1.  WORKER THREAD
# ──────────────────────────────────────────────

class AgentWorker(QThread):
    """Runs the blocking agent call off the GUI thread."""

    finished = Signal(str)
    error    = Signal(str)

    def __init__(self, prompt: str, parent=None):
        super().__init__(parent)
        self.prompt = prompt

    def run(self):
        try:
            result = manager_agent.run(self.prompt)
            self.finished.emit(str(result))
        except Exception as exc:
            self.error.emit(f"{type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────
# 2.  GUI
# ──────────────────────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RoboAdmin-AI")
        self.setMinimumSize(1280, 720)
        self._worker: AgentWorker | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # prompt
        prompt_row = QHBoxLayout()
        self.input_edit = QTextEdit()
        # One line (Qt only renders the FIRST line of a multi-line QTextEdit
        # placeholder) — it wraps, so all four hints stay visible.
        self.input_edit.setPlaceholderText(
            "• Configure Nginx (8080) & test endpoints in Docker • Setup/audit network configs (based on .txt or .cfg files) • Analyze file.txt (or file.sql) SQL schemas & database files"
        )
        self.input_edit.setFixedHeight(90)
        #prompt_row.addWidget(self.input_edit, stretch=1)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        self.combo.setFixedHeight(42)
        self.combo.setFont(QFont("Segoe UI", 11))
        # fetch FIRST, fill the list, then addItems (it copies at call time)
        models = list_ollama_models() or [DEFAULT_MODEL_ID]
        self.combo.addItems(models)
        if DEFAULT_MODEL_ID in models:
            self.combo.setCurrentText(DEFAULT_MODEL_ID)
        else:  # Ollama unreachable — keep the default, let the user know on hover
            self.combo.setToolTip("Ollama is not running — using fallback model.")
        # connect AFTER the initial selection so setup does not fire the slot
        self.combo.currentTextChanged.connect(self._on_model_changed)



        self.btn_run = QPushButton("Run Agent")
        self.btn_run.setMinimumHeight(46)
        self.btn_run.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.btn_run.setObjectName("run_button")
        self.btn_run.clicked.connect(self.on_run)

        self.btn_save = QPushButton("Save")
        self.btn_save.setMinimumHeight(46)
        self.btn_save.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.btn_save.setObjectName("save_button")
        self.btn_save.clicked.connect(self._save_to_file)

        self.btn_upload = QPushButton("Upload")
        self.btn_upload.setObjectName("upload_button")
        self.btn_upload.setMinimumHeight(46)
        self.btn_upload.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        self.btn_upload.clicked.connect(self._open_add)

        prompt_row.addWidget(self.combo)
        prompt_row.addWidget(self.btn_upload)
        prompt_row.addWidget(self.btn_run)
        prompt_row.addWidget(self.btn_save)

        root.addLayout(prompt_row)

        # output
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFont(QFont("Cascadia Code", 10))  # falls back to Consolas
        self.output_edit.setPlaceholderText("Agent output will appear here…")
        root.addWidget(self.input_edit,stretch=1)
        root.addWidget(self.output_edit, stretch=1)

        # status
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("status_label")   # neon-green, from the theme
        root.addWidget(self.status_label)

    def _on_model_changed(self, model_id: str):
        """Repoint all agents to the model selected in the combo box."""
        try:
            set_model_for_all_agents(model_id)
        except Exception as e:
            self.status_label.setText(f"Model switch failed: {e}")

    def _save_to_file(self):
        content = self.output_edit.toPlainText()
        if not content:
            QMessageBox.warning(self, "Warning", "Nothing to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Analysis",
            "analysis.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "Success", f"Saved to {path}")

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _open_add(self):
        if self._busy():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", "",
            "Config/Text Files (*.txt *.conf *.cfg *.ini *.yml *.yaml *.xml *.log);;"
            "PDF Documents (*.pdf);;"
            "All Files (*)",
        )
        if not file_path:
            return

        # ── 1. Copy first, so it survives any read failure ──────────────
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = UPLOADS_DIR / os.path.basename(file_path)

        try:
            shutil.copy2(file_path, str(dest_path))   # copy2 keeps timestamps too
            QMessageBox.information(self, "Success", "The document was uploaded.")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not copy file: {e}")
            return

        # ── 2. Read (failure here no longer prevents the copy) ──────────
        try:
            file_contents = read_document(str(dest_path))
        except Exception as e:
            self.output_edit.setText(f"Read error: {e}")
            QMessageBox.critical(self, "Error", f"Could not read file: {e}")
            return

        if not file_contents.strip():
            self.output_edit.setText("The file appears to be empty.")
            return

        self._start_analysis(file_contents, dest_path.name)

    def _start_analysis(self, file_contents: str, name: str = ""):
        """Show the uploaded file's text. (Hook for a future auto-analysis flow.)"""
        header = f"--- Uploaded file: {name} ---\n" if name else "--- Uploaded file ---\n"
        self.output_edit.setPlainText(header + file_contents[:2000])

    def on_run(self):
        prompt = self.input_edit.toPlainText().strip()
        if not prompt:
            self.status_label.setText("Please type a prompt first.")
            return

        self.output_edit.clear()
        self.btn_run.setEnabled(False)
        self.status_label.setText("Running agent… (may take several minutes)")
        self.output_edit.append("Agent is thinking…\n\n")

        self._worker = AgentWorker(prompt, self)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, text: str):
        sep = "=" * 60
        self.output_edit.append(f"\n{sep}\n=== Final answer ===\n{sep}\n{text}\n")
        self.status_label.setText("Done")
        self.btn_run.setEnabled(True)

    def _on_error(self, text: str):
        self.output_edit.append(f"\n❌  ERROR: {text}\n")
        self.status_label.setText("Error")
        self.btn_run.setEnabled(True)

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.wait(5_000)
        super().closeEvent(event)


# ──────────────────────────────────────────────
# 3.  ENTRY POINT  (GUI only – no top-level run)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # Make any CWD-relative access (e.g. in agent code) resolve against the app dir,
    # no matter where the app is launched from.
    os.chdir(APP_DIR)
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)
    # soft green-grey placeholder text (comfortable on the dark blue fields)
    pal = app.palette()
    pal.setColor(QPalette.PlaceholderText, QColor("#6fa58c"))
    app.setPalette(pal)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
