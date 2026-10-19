"""
GitHub Video Background Publisher Dialog for H3H Studio.
Allows creators to publish 4IFIR-compliant MP4 backgrounds to GitHub Releases and update the catalog.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QComboBox, QTextEdit, QProgressBar, QMessageBox,
    QFileDialog, QFrame, QGroupBox
)

from ..core.github_publisher import GitHubPublisher
from ..core.compliance import ComplianceValidator


class PublishWorkerThread(QThread):
    progress_status = Signal(str)
    finished = Signal(bool, dict, str)

    def __init__(
        self,
        video_path: Path,
        title_id: str,
        game_title: str,
        variant_name: str,
        style: str,
        author: str,
        token: str,
        repo: str,
        release_tag: str,
        description: str
    ):
        super().__init__()
        self.video_path = video_path
        self.title_id = title_id
        self.game_title = game_title
        self.variant_name = variant_name
        self.style = style
        self.author = author
        self.token = token
        self.repo = repo
        self.release_tag = release_tag
        self.description = description

    def run(self):
        try:
            res = GitHubPublisher.upload_video(
                video_path=self.video_path,
                title_id=self.title_id,
                game_title=self.game_title,
                variant_name=self.variant_name,
                style=self.style,
                author=self.author,
                token=self.token,
                repo=self.repo,
                release_tag=self.release_tag,
                description=self.description,
                progress_cb=self.progress_status.emit
            )
            self.finished.emit(True, res, "")
        except Exception as e:
            self.finished.emit(False, {}, str(e))


class GitHubPublishDialog(QDialog):
    def __init__(
        self,
        video_path: Optional[str] = None,
        title_id: str = "",
        game_title: str = "",
        style: str = "Animated Art",
        parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("Публикация видеофона на GitHub — H3H Studio")
        self.resize(760, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #121418;
                color: #FFFFFF;
            }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #1B1F26;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #00E5FF;
            }
            QPushButton {
                background-color: #252B35;
                border: 1px solid #2D3540;
                border-radius: 6px;
                padding: 9px 16px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #323B47;
            }
            QGroupBox {
                border: 1px solid #2D3540;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: bold;
                color: #00E5FF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
        """)

        token, user = GitHubPublisher.get_stored_credentials()
        self.default_token = token or ""
        self.default_user = user or "Holy3holy-dev"
        self._worker: Optional[PublishWorkerThread] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QLabel("🚀 Публикация видеофона в GitHub Releases и онлайн-каталог", self)
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(header)

        # 1. Video file selection
        file_box = QGroupBox("1. Видеофайл фонового видео (MP4)", self)
        file_layout = QVBoxLayout(file_box)
        pick_layout = QHBoxLayout()
        self.file_edit = QLineEdit(video_path or "", file_box)
        self.file_edit.setPlaceholderText("Путь к готовому MP4 файлу...")
        self.file_edit.textChanged.connect(self._validate_selected_file)
        pick_layout.addWidget(self.file_edit)

        browse_btn = QPushButton("Обзор...", file_box)
        browse_btn.clicked.connect(self._browse_file)
        pick_layout.addWidget(browse_btn)
        file_layout.addLayout(pick_layout)

        self.compliance_lbl = QLabel("Статус соответствия: Не проверено", file_box)
        self.compliance_lbl.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        file_layout.addWidget(self.compliance_lbl)
        layout.addWidget(file_box)

        # 2. Game & Variant Metadata
        meta_box = QGroupBox("2. Метаданные игры и варианта", self)
        meta_layout = QVBoxLayout(meta_box)

        row1 = QHBoxLayout()
        tid_layout = QVBoxLayout()
        tid_layout.addWidget(QLabel("Title ID игры (16 шестнадцатеричных символов):", meta_box))
        self.tid_edit = QLineEdit(title_id, meta_box)
        self.tid_edit.setPlaceholderText("01007EF00011E000")
        self.tid_edit.setFont(QFont("Consolas", 11))
        tid_layout.addWidget(self.tid_edit)
        row1.addLayout(tid_layout)

        game_layout = QVBoxLayout()
        game_layout.addWidget(QLabel("Название игры:", meta_box))
        self.game_edit = QLineEdit(game_title, meta_box)
        self.game_edit.setPlaceholderText("The Legend of Zelda...")
        game_layout.addWidget(self.game_edit)
        row1.addLayout(game_layout)
        meta_layout.addLayout(row1)

        row2 = QHBoxLayout()
        var_layout = QVBoxLayout()
        var_layout.addWidget(QLabel("Название варианта (например, Opening Loop):", meta_box))
        self.var_edit = QLineEdit(meta_box)
        self.var_edit.setPlaceholderText("Main Theme Animated Loop")
        var_layout.addWidget(self.var_edit)
        row2.addLayout(var_layout)

        style_layout = QVBoxLayout()
        style_layout.addWidget(QLabel("Категория / Стиль:", meta_box))
        self.style_combo = QComboBox(meta_box)
        self.style_combo.addItems(["Animated Art", "Cinematic", "Gameplay", "Minimal", "Dark", "Retro"])
        self.style_combo.setCurrentText(style)
        style_layout.addWidget(self.style_combo)
        row2.addLayout(style_layout)

        author_layout = QVBoxLayout()
        author_layout.addWidget(QLabel("Автор видеофона:", meta_box))
        self.author_edit = QLineEdit(self.default_user, meta_box)
        author_layout.addWidget(self.author_edit)
        row2.addLayout(author_layout)
        meta_layout.addLayout(row2)

        desc_layout = QVBoxLayout()
        desc_layout.addWidget(QLabel("Краткое описание / теги (необязательно):", meta_box))
        self.desc_edit = QLineEdit(meta_box)
        self.desc_edit.setPlaceholderText("Плавное зацикливание, 60fps, высокое качество")
        desc_layout.addWidget(self.desc_edit)
        meta_layout.addLayout(desc_layout)

        layout.addWidget(meta_box)

        # 3. GitHub repository & Authentication
        git_box = QGroupBox("3. Параметры GitHub", self)
        git_layout = QVBoxLayout(git_box)

        git_row = QHBoxLayout()
        repo_layout = QVBoxLayout()
        repo_layout.addWidget(QLabel("Репозиторий GitHub:", git_box))
        self.repo_edit = QLineEdit(GitHubPublisher.DEFAULT_REPO, git_box)
        repo_layout.addWidget(self.repo_edit)
        git_row.addLayout(repo_layout)

        tag_layout = QVBoxLayout()
        tag_layout.addWidget(QLabel("Тег релиза:", git_box))
        self.tag_edit = QLineEdit(GitHubPublisher.DEFAULT_TAG, git_box)
        tag_layout.addWidget(self.tag_edit)
        git_row.addLayout(tag_layout)
        git_layout.addLayout(git_row)

        tok_layout = QVBoxLayout()
        tok_layout.addWidget(QLabel("GitHub Personal Access Token (PAT):", git_box))
        self.token_edit = QLineEdit(self.default_token, git_box)
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxx")
        tok_layout.addWidget(self.token_edit)

        if self.default_token:
            tok_hint = QLabel("✓ Токен автоматически получен из диспетчера учётных данных Windows", git_box)
            tok_hint.setStyleSheet("color: #10B981; font-size: 11px;")
            tok_layout.addWidget(tok_hint)

        git_layout.addLayout(tok_layout)
        layout.addWidget(git_box)

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("", self)
        self.status_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        layout.addWidget(self.status_lbl)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.publish_btn = QPushButton("🚀 Опубликовать на GitHub", self)
        self.publish_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 14px;")
        self.publish_btn.clicked.connect(self._start_publish)
        btn_layout.addWidget(self.publish_btn)

        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        if video_path:
            self._validate_selected_file(video_path)

    def _browse_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Выберите готовый видеофон MP4", "", "MP4 Videos (*.mp4)")
        if f:
            self.file_edit.setText(f)

    def _validate_selected_file(self, path_str: str):
        p = Path(path_str.strip())
        if not p.exists() or not p.is_file():
            self.compliance_lbl.setText("Файл не найден")
            self.compliance_lbl.setStyleSheet("color: #EF4444;")
            return

        comp = ComplianceValidator.validate_mp4(p)
        if comp.is_valid:
            self.compliance_lbl.setText(
                f"✓ Соответствует 4IFIR: {comp.width}x{comp.height} @{round(comp.fps)}fps, кодек: {comp.codec}, размер: {p.stat().st_size / 1024 / 1024:.2f} MB"
            )
            self.compliance_lbl.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            err = "; ".join(comp.errors)
            self.compliance_lbl.setText(f"⚠ Предупреждение 4IFIR: {err}")
            self.compliance_lbl.setStyleSheet("color: #F59E0B;")

    def _start_publish(self):
        video_p = Path(self.file_edit.text().strip())
        if not video_p.exists():
            QMessageBox.warning(self, "Ошибка", "Выберите существующий MP4 файл для загрузки!")
            return

        tid = self.tid_edit.text().strip().upper()
        if not tid or len(tid) != 16 or not tid.startswith("0100"):
            QMessageBox.warning(self, "Ошибка", "Title ID должен состоять из 16 шестнадцатеричных символов и начинаться с 0100!")
            return

        game = self.game_edit.text().strip()
        if not game:
            QMessageBox.warning(self, "Ошибка", "Укажите название игры!")
            return

        var_name = self.var_edit.text().strip()
        if not var_name:
            var_name = "Default Background Loop"

        token = self.token_edit.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Укажите GitHub Personal Access Token (PAT)!")
            return

        repo = self.repo_edit.text().strip()
        tag = self.tag_edit.text().strip() or "v1.0.0"
        author = self.author_edit.text().strip() or "Holy3holy-dev"
        style = self.style_combo.currentText()
        desc = self.desc_edit.text().strip()

        self.publish_btn.setEnabled(False)
        self.progress_bar.setVisible(True)

        self._worker = PublishWorkerThread(
            video_path=video_p,
            title_id=tid,
            game_title=game,
            variant_name=var_name,
            style=style,
            author=author,
            token=token,
            repo=repo,
            release_tag=tag,
            description=desc
        )
        self._worker.progress_status.connect(self._on_progress_status)
        self._worker.finished.connect(self._on_publish_finished)
        self._worker.start()

    def _on_progress_status(self, text: str):
        self.status_lbl.setText(text)

    def _on_publish_finished(self, success: bool, res: dict, err: str):
        self.publish_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self.status_lbl.setText("✓ Успешно опубликовано!")
            msg = (
                f"Видеофон успешно загружен на GitHub!\n\n"
                f"• Title ID: {res['titleId']}\n"
                f"• Имя для 4IFIR на Switch: {res['targetCoverName']}\n"
                f"• Путь на SD-карте: {res['sdCardPath']}\n"
                f"• SHA-256: {res['sha256']}\n"
                f"• Размер: {res['sizeBytes'] / 1024 / 1024:.2f} MB\n\n"
                f"Ссылка на скачивание:\n{res['downloadUrl']}\n\n"
                f"Запись добавлена в каталог и доступна в онлайн-библиотеке и Downloader!"
            )
            QMessageBox.information(self, "Успех", msg)
            self.accept()
        else:
            self.status_lbl.setText("Ошибка публикации")
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось опубликовать видеофон на GitHub:\n\n{err}")
