import os
import tempfile
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDateEdit,
    QFileDialog, QListWidget, QMessageBox,
    QFrame, QSplitter, QStatusBar, QGroupBox,
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QPixmap

from ssh_client import SSHClient, load_settings
from image_processor import convert_to_webp, is_supported_image
from html_editor import (
    add_product_to_html,
    add_process_to_html,
    PROCESS_CAPTIONS,
)
from settings_dialog import SettingsDialog


class GalleryManager(QMainWindow):
    """서보테크놀로지 갤러리 관리 메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("📦 서보테크놀로지 갤러리 관리")
        self.setMinimumSize(900, 650)
        self.resize(1000, 720)

        self.ssh = SSHClient()
        self.selected_images: list[str] = []  # 선택된 로컬 이미지 경로
        self.current_preview_index: int = 0   # 현재 미리보기 중인 이미지 인덱스
        self.converted_files: list[str] = []  # 변환된 WebP 파일 (cleanup용)
        self.next_image_number = 0
        self.selected_process_folder: Optional[str] = None  # 선택된 공정 폴더
        self.process_folders: list[str] = []  # 원격 폴더 목록

        self._build_ui()
        self._update_connection_status()
        self._apply_styles()

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background: #f3f6fa; }
            QGroupBox {
                font-weight: 600;
                border: 1px solid #d9e2ec;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 16px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #334155;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                border: 1px solid #cbd5e1;
                background: #ffffff;
                color: #1e293b;
            }
            QPushButton:hover {
                background: #f1f5f9;
                border-color: #94a3b8;
            }
            QPushButton#connectBtn {
                background: #3b82c4;
                color: white;
                border: 1px solid #2f6fa8;
            }
            QPushButton#connectBtn:hover {
                background: #2f6fa8;
            }
            QPushButton#connectBtn:disabled {
                background: #94a3b8;
                border-color: #94a3b8;
            }
            QPushButton#addBtn {
                background: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                padding: 10px 24px;
                font-size: 14px;
            }
            QPushButton#addBtn:hover {
                background: #1d4ed8;
            }
            QPushButton#addBtn:disabled {
                background: #94a3b8;
                border-color: #94a3b8;
            }
            QLineEdit, QTextEdit, QDateEdit {
                padding: 8px;
                border: 1px solid #d9e2ec;
                border-radius: 6px;
                background: #ffffff;
                color: #1e293b;
            }
            QListWidget {
                border: 1px solid #d9e2ec;
                border-radius: 6px;
                background: #ffffff;
            }
            QStatusBar { background: #dce6f2; color: #1e293b; }
            QTextEdit#logArea {
                background: #f8fafc;
                color: #334155;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 12px;
            }
            QSplitter::handle { background: #d9e2ec; width: 2px; }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 상단: 연결 바
        main_layout.addWidget(self._build_connection_bar())

        # 중앙: 메인 콘텐츠 (분할)
        splitter = QSplitter(Qt.Horizontal)

        # 왼쪽: 이미지 선택 영역
        left_widget = self._build_image_section()
        splitter.addWidget(left_widget)

        # 오른쪽: 제품 정보 + 로그
        right_widget = self._build_info_section()
        splitter.addWidget(right_widget)

        splitter.setSizes([500, 500])
        main_layout.addWidget(splitter, 1)

        # 하단: 액션 버튼
        main_layout.addWidget(self._build_action_bar())

        # 상태바
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_connection_bar(self):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 4px; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        self.conn_label = QLabel("● 연결 안됨")
        self.conn_label.setStyleSheet("color: #ef4444; font-weight: 600;")
        layout.addWidget(self.conn_label)

        layout.addStretch()

        self.settings_btn = QPushButton("⚙️ 설정")
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        self.connect_btn = QPushButton("🔌 연결")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_btn)

        return bar

    def _build_image_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("📷 이미지")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(8)

        # 버튼 행
        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("➕ 이미지 파일 선택")
        self.select_btn.clicked.connect(self.select_images)
        btn_row.addWidget(self.select_btn)

        self.clear_btn = QPushButton("🗑️ 초기화")
        self.clear_btn.clicked.connect(self.clear_images)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch()
        self.img_count_label = QLabel("선택한 이미지: 0개")
        self.img_count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        btn_row.addWidget(self.img_count_label)
        group_layout.addLayout(btn_row)

        # 미리보기 (크게)
        preview_frame = QWidget()
        preview_frame.setStyleSheet("background: transparent;")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(4)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_label = QLabel("이미지를 선택하면 미리보기가 표시됩니다.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        self.preview_label.setStyleSheet(
            "background: #f8fafc; border: 1px dashed #cbd5e1; "
            "border-radius: 6px; color: #94a3b8;"
        )
        preview_layout.addWidget(self.preview_label, 1)

        # 이전/다음 버튼
        nav_row = QHBoxLayout()
        nav_row.setSpacing(4)
        self.prev_btn = QPushButton("◀ 이전")
        self.prev_btn.setFixedHeight(28)
        self.prev_btn.setStyleSheet(
            "QPushButton { padding: 2px 12px; font-size: 12px; font-weight: 500; }"
        )
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._prev_preview)
        nav_row.addWidget(self.prev_btn)

        self.preview_index_label = QLabel("")
        self.preview_index_label.setAlignment(Qt.AlignCenter)
        self.preview_index_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        nav_row.addWidget(self.preview_index_label, 1)

        self.next_btn = QPushButton("다음 ▶")
        self.next_btn.setFixedHeight(28)
        self.next_btn.setStyleSheet(
            "QPushButton { padding: 2px 12px; font-size: 12px; font-weight: 500; }"
        )
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._next_preview)
        nav_row.addWidget(self.next_btn)
        preview_layout.addLayout(nav_row)

        group_layout.addWidget(preview_frame, 1)

        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #e2e8f0;")
        group_layout.addWidget(sep)

        # 원격 폴더 목록 (공정 사진 대상) - 글씨색 명시
        folder_label = QLabel("라즈베리파이 폴더 (⚙️ 공정 사진 추가 대상)")
        folder_label.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        group_layout.addWidget(folder_label)

        self.process_folder_list = QListWidget()
        self.process_folder_list.setMinimumHeight(90)
        self.process_folder_list.setStyleSheet(
            "QListWidget { background: #ffffff; color: #1e293b; "
            "border: 1px solid #e2e8f0; border-radius: 4px; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background: #dbeafe; color: #1e40af; }"
            "QListWidget::item:hover { background: #f1f5f9; }"
        )
        self.process_folder_list.itemClicked.connect(self._on_process_folder_selected)
        group_layout.addWidget(self.process_folder_list)

        layout.addWidget(group)
        return widget

    def _build_info_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # right splitter (제품 정보 | 작업 로그)
        right_splitter = QSplitter(Qt.Vertical)

        # 제품 정보
        info_group = QGroupBox("📝 제품 정보")
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(8)

        info_layout.addWidget(QLabel("규격:"), 0, 0)
        self.spec_input = QLineEdit()
        self.spec_input.setPlaceholderText("예: 25G-RW(0.5x0.26)x22.4mm")
        info_layout.addWidget(self.spec_input, 0, 1)

        info_layout.addWidget(QLabel("등록일:"), 1, 0)
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setDisplayFormat("yyyy-MM-dd")
        info_layout.addWidget(self.date_input, 1, 1)

        info_layout.addWidget(QLabel("다음 번호:"), 2, 0)
        self.number_label = QLabel("연결 후 확인")
        self.number_label.setStyleSheet("font-weight: 600; color: #2563eb;")
        info_layout.addWidget(self.number_label, 2, 1)

        # 제품 정보는 컴팩트하게 — 여분 stretch 제거
        right_splitter.addWidget(info_group)

        # 로그 영역 (크게)
        log_group = QGroupBox("📋 작업 로그")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setReadOnly(True)
        # 최대높이 제한 제거 — 로그를 넉넉히 보여줌
        log_layout.addWidget(self.log_area)
        right_splitter.addWidget(log_group)

        right_splitter.setSizes([180, 300])
        layout.addWidget(right_splitter, 1)

        return widget

    def _build_action_bar(self):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        self.photo_add_btn = QPushButton("📷 사진 추가")
        self.photo_add_btn.setObjectName("addBtn")
        self.photo_add_btn.setEnabled(False)
        self.photo_add_btn.clicked.connect(self.add_photos)
        layout.addWidget(self.photo_add_btn)

        layout.addStretch()

        self.refresh_btn = QPushButton("🔄 새로고침")
        self.refresh_btn.clicked.connect(self.refresh_data)
        layout.addWidget(self.refresh_btn)

        return bar

    # ======== 이벤트 핸들러 ========

    def log(self, message: str):
        self.log_area.append(message)
        self.status_bar.showMessage(message, 5000)

    def toggle_connection(self):
        if self.ssh.is_connected():
            self.ssh.disconnect()
            self._update_connection_status()
            self.log("🔌 연결 종료")
        else:
            self.connect_btn.setEnabled(False)
            self.connect_btn.setText("⏳ 연결중...")
            success, msg = self.ssh.connect()
            self.connect_btn.setEnabled(True)
            if success:
                self._update_connection_status()
                self.log(msg)
                self.load_remote_info()
                self.refresh_process_folders()
            else:
                self.connect_btn.setText("🔌 연결")
                QMessageBox.warning(self, "연결 실패", msg)
                self._update_connection_status()

    def _update_connection_status(self):
        if self.ssh.is_connected():
            host = self.ssh.settings.get("host", "")
            self.conn_label.setText(f"● 연결됨 ({host})")
            self.conn_label.setStyleSheet("color: #16a34a; font-weight: 600;")
            self.connect_btn.setText("🔌 연결 종료")
            self.photo_add_btn.setEnabled(True)
            self._update_add_button()
        else:
            self.conn_label.setText("● 연결 안됨")
            self.conn_label.setStyleSheet("color: #ef4444; font-weight: 600;")
            self.connect_btn.setText("🔌 연결")
            self.photo_add_btn.setEnabled(False)
            self.number_label.setText("연결 후 확인")

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.ssh.settings = load_settings()
            # 연결 끊기
            if self.ssh.is_connected():
                self.ssh.disconnect()
                self._update_connection_status()
            self.log("⚙️ 설정 저장됨")
            # 경로 라벨 갱신
            self.refresh_process_folders()

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "이미지 파일 선택",
            "",
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp);;모든 파일 (*.*)",
        )
        if files:
            valid = [f for f in files if is_supported_image(f)]
            if not valid:
                QMessageBox.warning(self, "지원 안됨", "지원하는 이미지 형식이 없습니다.\n(JPG, PNG, BMP, TIFF, WebP)")
                return
            self.selected_images = valid
            self.current_preview_index = 0
            self.img_count_label.setText(f"선택한 이미지: {len(valid)}개")
            self._show_current_preview()
            self.log(f"📎 {len(valid)}개 이미지 선택됨")
            self._update_process_add_button()

    def clear_images(self):
        self.selected_images = []
        self.current_preview_index = 0
        self.img_count_label.setText("선택한 이미지: 0개")
        self.preview_label.setText("이미지를 선택하면 미리보기가 표시됩니다.")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setStyleSheet(
            "background: #f8fafc; border: 1px dashed #cbd5e1; "
            "border-radius: 6px; color: #94a3b8;"
        )
        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.preview_index_label.setText("")
        self._update_process_add_button()

    def _show_current_preview(self):
        """현재 인덱스의 이미지를 미리보기에 표시하고 네비게이션 버튼 상태 갱신"""
        n = len(self.selected_images)
        if n == 0:
            return
        idx = self.current_preview_index
        img_path = self.selected_images[idx]
        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                360, 280,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet(
                "background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;"
            )
        else:
            self.preview_label.setText(f"미리보기 불가\n{os.path.basename(img_path)}")

        # 네비게이션 버튼 상태 (if/else 밖에서 항상 실행)
        self.prev_btn.setEnabled(n > 1 and idx > 0)
        self.next_btn.setEnabled(n > 1 and idx < n - 1)
        self.preview_index_label.setText(f"{idx + 1} / {n}")

    def _update_process_add_button(self):
        """📷 사진 추가 버튼 활성화 조건 체크 (폴더 선택 + 이미지 선택)"""
        has_folder = self.selected_process_folder is not None
        has_images = len(self.selected_images) > 0
        self.photo_add_btn.setEnabled(has_folder and has_images)

    def _prev_preview(self):
        if self.current_preview_index > 0:
            self.current_preview_index -= 1
            self._show_current_preview()

    def _next_preview(self):
        if self.current_preview_index < len(self.selected_images) - 1:
            self.current_preview_index += 1
            self._show_current_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 미리보기 리사이즈 - 부드러운 처리를 위해 QTimer 사용 가능
        if not self.preview_label.pixmap().isNull():
            scaled = self.preview_label.pixmap().scaled(
                self.preview_label.width(),
                180,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            temp = self.preview_label.pixmap()
            self.preview_label.setPixmap(scaled)

    def load_remote_info(self):
        """원격 서버에서 정보 로드"""
        if not self.ssh.is_connected():
            return

        # 다음 이미지 번호 (내부 저장, 폴더 선택 시 표시)
        self.next_image_number = self.ssh.get_next_image_number()
        self.refresh_btn.setEnabled(True)

        # 이미 선택된 폴더가 있다면 번호 갱신
        self._update_number_display()

    def _update_number_display(self):
        """선택된 폴더 기준으로 다음 번호 표시"""
        folder = self.selected_process_folder
        if not folder or not self.ssh.is_connected():
            self.number_label.setText("폴더 선택 후 표시")
            return
        try:
            if folder == "sustube":
                self.number_label.setText(f"sustube{self.next_image_number}")
                self.log(f"  🔢 다음 번호: sustube{self.next_image_number}")
            else:
                next_num = self.ssh.get_next_process_number(folder)
                self.number_label.setText(f"{folder}{next_num}")
                self.log(f"  🔢 다음 번호: {folder}{next_num}")
        except Exception as e:
            self.number_label.setText(f"{folder}?")
            self.log(f"  ⚠️ 번호 확인 실패: {e}")

    def refresh_data(self):
        self.load_remote_info()
        self.refresh_process_folders()

    def _on_process_folder_selected(self, item):
        """공정 폴더 선택 시"""
        self.selected_process_folder = item.text()
        self._update_add_button()
        self.log(f"📁 선택한 폴더: {self.selected_process_folder}")

        # 선택한 폴더 기준 다음 번호 표시
        self._update_number_display()

    def _update_add_button(self):
        """사진 추가 버튼 활성화 조건 체크"""
        has_folder = self.selected_process_folder is not None
        has_images = len(self.selected_images) > 0
        self.photo_add_btn.setEnabled(has_folder and has_images)

    def refresh_process_folders(self):
        """라즈베리파이의 이미지 폴더 하위 디렉토리 목록 갱신 (SSH)"""
        self.process_folder_list.clear()
        self.selected_process_folder = None
        self._update_add_button()
        self._update_number_display()

        if not self.ssh.is_connected():
            self.process_folder_list.addItem("⚠️ 라즈베리파이에 연결 후 사용해주세요.")
            return

        pi_dir = self.ssh.settings.get("pi_image_dir", "")
        if not pi_dir:
            self.process_folder_list.addItem("⚠️ 설정에서 라즈베리파이 이미지 폴더 경로를 지정해주세요. (⚙️ 설정)")
            return

        try:
            success, dirs = self.ssh.list_remote_directories(pi_dir)
            if not success:
                self.process_folder_list.addItem("⚠️ 폴더 목록 읽기 실패")
                return

            self.process_folders = sorted(dirs)
            if not self.process_folders:
                self.process_folder_list.addItem("⚠️ 하위 폴더가 없습니다.")
                return
            for d in self.process_folders:
                self.process_folder_list.addItem(d)
            self.log(f"📂 라즈베리파이 폴더: {len(self.process_folders)}개 하위 폴더 발견")
        except Exception as e:
            self.process_folder_list.addItem(f"⚠️ 오류: {e}")
            self.log(f"⚠️ 폴더 목록 오류: {e}")

    def add_photos(self):
        """사진 추가 - 선택한 폴더에 따라 제품/공정 자동 분기"""
        folder = self.selected_process_folder
        if not folder:
            QMessageBox.warning(self, "선택 필요", "라즈베리파이 폴더 목록에서 폴더를 선택해주세요.")
            return
        if folder == "sustube":
            self.add_to_gallery()
        else:
            self.add_process_photos()

    def add_process_photos(self):
        """선택한 공정 폴더에 PC 이미지를 WebP 변환 → 업로드"""
        if not self.ssh.is_connected():
            QMessageBox.warning(self, "연결 필요", "먼저 라즈베리파이에 연결해주세요.")
            return

        folder = self.selected_process_folder
        if not folder:
            QMessageBox.warning(self, "선택 필요", "공정 사진 폴더를 선택해주세요.")
            return

        if not self.selected_images:
            QMessageBox.warning(self, "선택 필요", "PC에서 업로드할 사진을 선택해주세요.\n(➕ 이미지 파일 선택 버튼)")
            return

        reply = QMessageBox.question(
            self, "공정 사진 추가",
            f"📁 대상 폴더: {folder} ({PROCESS_CAPTIONS.get(folder, folder)})\n"
            f"🖼️ {len(self.selected_images)}개 이미지 업로드\n"
            f"계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.log(f"🔄 공정 사진 처리 시작... (폴더: {folder}, {len(self.selected_images)}개)")
        self.photo_add_btn.setEnabled(False)
        self.photo_add_btn.setText("⏳ 처리중...")

        import shutil
        temp_dir = tempfile.mkdtemp(prefix=f"servo_{folder}_")
        image_numbers = []
        full_upload_paths = []
        thumb_upload_paths = []

        try:
            # 원격에서 마지막 번호 확인
            next_num = self.ssh.get_next_process_number(folder)
            self.log(f"  🔢 다음 번호: {folder}{next_num}")

            # 1. 로컬 이미지 → WebP 변환
            for i, img_path in enumerate(self.selected_images):
                base_name = f"{folder}{next_num + i}"
                full_path, thumb_path, error = convert_to_webp(
                    img_path, temp_dir, base_name
                )
                if error:
                    raise Exception(f"WebP 변환 실패 ({base_name}): {error}")

                image_numbers.append(next_num + i)
                full_upload_paths.append(full_path)
                thumb_upload_paths.append(thumb_path)
                self.log(f"  ✅ {base_name}.webp 변환 완료")

            # 2. WebP 업로드
            self.log("📤 WebP 업로드 중...")
            remote_base = self.ssh.get_remote_process_folder(folder)

            for full_path, thumb_path, num in zip(
                full_upload_paths, thumb_upload_paths, image_numbers
            ):
                remote_full = f"{remote_base}/{folder}{num}.webp"
                ok, msg = self.ssh.upload_file(full_path, remote_full)
                if not ok:
                    raise Exception(f"업로드 실패 ({folder}{num}.webp): {msg}")

                remote_thumb = f"{remote_base}/thumbs/{folder}{num}_thumb.webp"
                ok, msg = self.ssh.upload_file(thumb_path, remote_thumb)
                if not ok:
                    raise Exception(f"썸네일 업로드 실패 ({folder}{num}_thumb.webp): {msg}")
                self.log(f"  ✅ {folder}{num}.webp 업로드 완료")

            # 3. gallery.html 수정
            self.log("📝 gallery.html 업데이트 중...")
            remote_file = self.ssh.get_remote_gallery_path()
            html, err = self.ssh.read_remote_file(remote_file)
            if not html:
                raise Exception(f"gallery.html 읽기 실패: {err}")

            modified_html, error = add_process_to_html(html, folder, image_numbers)
            if error:
                raise Exception(error)

            ok, msg = self.ssh.write_remote_file(remote_file, modified_html)
            if not ok:
                raise Exception(msg)

            # 4. 완료
            self.log(f"🎉 공정 사진 업데이트 완료!")
            self.log(f"   폴더: {folder}, 이미지: {len(image_numbers)}개")

            QMessageBox.information(
                self, "✅ 완료",
                f"⚙️ 공정 사진 추가 완료!\n\n"
                f"대상 폴더: {folder}\n"
                f"이미지: {len(image_numbers)}개\n"
                f"파일명: {', '.join(f'{folder}{n}.webp' for n in image_numbers)}"
            )

        except Exception as e:
            self.log(f"❌ 오류 발생: {e}")
            QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다.\n\n{e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.photo_add_btn.setEnabled(True)
            self.photo_add_btn.setText("📷 사진 추가")
            self.load_remote_info()

    def add_to_gallery(self):
        """갤러리에 새 제품 추가"""
        if not self.ssh.is_connected():
            QMessageBox.warning(self, "연결 필요", "먼저 라즈베리파이에 연결해주세요.")
            return

        spec = self.spec_input.text().strip()
        if not spec:
            QMessageBox.warning(self, "입력 확인", "제품 규격을 입력해주세요.")
            return

        if not self.selected_images:
            QMessageBox.warning(self, "입력 확인", "이미지를 선택해주세요.")
            return

        # 1. 이미지 변환 (WebP)
        self.log(f"🔄 WebP 변환 시작... ({len(self.selected_images)}개)")
        self.photo_add_btn.setEnabled(False)
        self.photo_add_btn.setText("⏳ 처리중...")

        temp_dir = tempfile.mkdtemp(prefix="servo_gallery_")
        image_numbers = []
        full_upload_paths = []
        thumb_upload_paths = []

        try:
            for i, img_path in enumerate(self.selected_images):
                base_name = f"sustube{self.next_image_number + i}"
                full_path, thumb_path, error = convert_to_webp(
                    img_path, temp_dir, base_name
                )
                if error:
                    raise Exception(error)

                image_numbers.append(self.next_image_number + i)
                full_upload_paths.append(full_path)
                thumb_upload_paths.append(thumb_path)
                self.log(f"  ✅ {base_name}.webp 변환 완료")

            # 2. 이미지 업로드
            self.log("📤 이미지 업로드 중...")
            remote_base = f'{self.ssh.settings["remote_path"]}/images/sustube'

            for full_path, thumb_path, num in zip(
                full_upload_paths, thumb_upload_paths, image_numbers
            ):
                # Full 이미지
                remote_full = f"{remote_base}/sustube{num}.webp"
                ok, msg = self.ssh.upload_file(full_path, remote_full)
                if not ok:
                    raise Exception(msg)

                # Thumbnail
                remote_thumb = f"{remote_base}/thumbs/sustube{num}_thumb.webp"
                ok, msg = self.ssh.upload_file(thumb_path, remote_thumb)
                if not ok:
                    raise Exception(msg)

                self.log(f"  ✅ sustube{num}.webp 업로드 완료")

            # 3. gallery.html 수정
            self.log("📝 gallery.html 업데이트 중...")
            date_str = self.date_input.date().toString("yyyy-MM-dd")
            remote_file = self.ssh.get_remote_gallery_path()
            html, err = self.ssh.read_remote_file(remote_file)
            if not html:
                raise Exception(f"gallery.html 읽기 실패: {err}")

            modified_html, error = add_product_to_html(html, spec, date_str, image_numbers)
            if error:
                raise Exception(error)

            # 4. 수정된 HTML 업로드
            ok, msg = self.ssh.write_remote_file(remote_file, modified_html)
            if not ok:
                raise Exception(msg)

            # 5. 완료
            self.next_image_number = max(image_numbers) + 1
            self.number_label.setText(f"sustube{self.next_image_number}")

            self.log(f"🎉 갤러리 업데이트 완료!")
            self.log(f"   제품: {spec}")
            self.log(f"   이미지: {', '.join(f'sustube{n}' for n in image_numbers)}")

            QMessageBox.information(
                self, "✅ 완료",
                f"갤러리 업데이트 완료!\n\n제품: {spec}\n이미지: {len(image_numbers)}개\n파일: sustube{image_numbers[0]} ~ sustube{image_numbers[-1]}"
            )

            # 입력 초기화
            self.clear_images()
            self.spec_input.clear()
            self.load_remote_info()

        except Exception as e:
            self.log(f"❌ 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다:\n{str(e)}")
        finally:
            # 임시 디렉토리 정리
            import shutil
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            self.photo_add_btn.setEnabled(True)
            self.photo_add_btn.setText("📷 사진 추가")
