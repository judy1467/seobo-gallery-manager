"""메인 윈도우 - 갤러리 관리 프로그램"""

import os
import re
import tempfile
from datetime import date
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QDateEdit,
    QFileDialog, QListWidget, QListWidgetItem, QMessageBox,
    QFrame, QSplitter, QStatusBar, QGroupBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtGui import QPixmap, QIcon

from ssh_client import SSHClient, load_settings
from image_processor import convert_to_webp, is_supported_image
from html_editor import (
    find_product_groups_js,
    add_product_to_html,
    add_process_to_html,
    find_max_image_number,
    get_all_captions,
    PROCESS_FOLDERS,
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
        self.converted_files: list[str] = []  # 변환된 WebP 파일 (cleanup용)
        self.next_image_number = 0
        self.selected_process_folder: Optional[str] = None  # 선택된 공정 폴더
        self.process_folders: list[str] = []  # 로컬 이미지 폴더 목록

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

        # === 제품 사진 ===
        product_group = QGroupBox("📦 제품 사진")
        product_layout = QVBoxLayout(product_group)
        product_layout.setSpacing(8)

        btn_row = QHBoxLayout()
        self.select_btn = QPushButton("➕ 이미지 파일 선택")
        self.select_btn.clicked.connect(self.select_images)
        btn_row.addWidget(self.select_btn)

        self.clear_btn = QPushButton("🗑️ 초기화")
        self.clear_btn.clicked.connect(self.clear_images)
        btn_row.addWidget(self.clear_btn)
        product_layout.addLayout(btn_row)

        self.image_list = QListWidget()
        self.image_list.setSpacing(2)
        self.image_list.setMinimumHeight(150)
        product_layout.addWidget(self.image_list, 1)

        self.preview_label = QLabel("이미지를 선택하면 미리보기가 표시됩니다.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(140)
        self.preview_label.setStyleSheet("background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; color: #94a3b8;")
        self.preview_label.setScaledContents(True)
        product_layout.addWidget(self.preview_label)

        layout.addWidget(product_group)

        # === 공정 사진 ===
        process_group = QGroupBox("⚙️ 공정 사진")
        process_layout = QVBoxLayout(process_group)
        process_layout.setSpacing(6)

        self.process_folder_list = QListWidget()
        self.process_folder_list.setMinimumHeight(120)
        self.process_folder_list.itemClicked.connect(self._on_process_folder_selected)
        process_layout.addWidget(self.process_folder_list, 1)

        refresh_btn = QHBoxLayout()
        self.process_refresh_btn = QPushButton("🔄 폴더 새로고침")
        self.process_refresh_btn.clicked.connect(self.refresh_process_folders)
        refresh_btn.addWidget(self.process_refresh_btn)
        refresh_btn.addStretch()
        process_layout.addLayout(refresh_btn)

        layout.addWidget(process_group)
        return widget

    def _build_info_section(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

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

        info_layout.setRowStretch(3, 1)
        layout.addWidget(info_group)

        # 등록된 제품 수
        count_group = QGroupBox("📊 현황")
        count_layout = QVBoxLayout(count_group)
        self.count_label = QLabel("연결 후 확인")
        count_layout.addWidget(self.count_label)
        self.process_count_label = QLabel("")
        self.process_count_label.setStyleSheet("color: #6b7280;")
        count_layout.addWidget(self.process_count_label)
        layout.addWidget(count_group)

        # 로그 영역
        log_group = QGroupBox("📋 작업 로그")
        log_layout = QVBoxLayout(log_group)
        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(180)
        log_layout.addWidget(self.log_area)
        layout.addWidget(log_group)

        return widget

    def _build_action_bar(self):
        bar = QFrame()
        bar.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; }")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)

        self.add_btn = QPushButton("✅ 제품 사진 추가")
        self.add_btn.setObjectName("addBtn")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self.add_to_gallery)
        layout.addWidget(self.add_btn)

        self.process_add_btn = QPushButton("⚙️ 공정 사진 추가")
        self.process_add_btn.setObjectName("addBtn")
        self.process_add_btn.setEnabled(False)
        self.process_add_btn.clicked.connect(self.add_process_photos)
        layout.addWidget(self.process_add_btn)

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
            self.add_btn.setEnabled(True)
            self.process_add_btn.setEnabled(True)
        else:
            self.conn_label.setText("● 연결 안됨")
            self.conn_label.setStyleSheet("color: #ef4444; font-weight: 600;")
            self.connect_btn.setText("🔌 연결")
            self.add_btn.setEnabled(False)
            self.process_add_btn.setEnabled(False)
            self.number_label.setText("연결 후 확인")
            self.count_label.setText("연결 후 확인")

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self.ssh.settings = load_settings()
            # 연결 끊기
            if self.ssh.is_connected():
                self.ssh.disconnect()
                self._update_connection_status()
            self.log("⚙️ 설정 저장됨")

    def select_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "이미지 파일 선택",
            "",
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.tiff *.tif *.webp);;모든 파일 (*.*)",
        )
        if files:
            # 지원 포맷만 필터링
            valid = [f for f in files if is_supported_image(f)]
            if not valid:
                QMessageBox.warning(self, "지원 안됨", "지원하는 이미지 형식이 없습니다.\n(JPG, PNG, BMP, TIFF, WebP)")
                return
            self.selected_images = valid
            self._refresh_image_list()
            self._show_preview(valid[0])
            self.log(f"📎 {len(valid)}개 이미지 선택됨")

    def clear_images(self):
        self.selected_images = []
        self.image_list.clear()
        self.preview_label.setText("이미지를 선택하면 미리보기가 표시됩니다.")
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setStyleSheet("background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 6px; color: #94a3b8;")

    def _refresh_image_list(self):
        self.image_list.clear()
        for path in self.selected_images:
            item = QListWidgetItem(os.path.basename(path))
            self.image_list.addItem(item)
        if self.selected_images:
            self.image_list.setCurrentRow(0)

    def _show_preview(self, path: str):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.preview_label.width(),
                180,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setStyleSheet("background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")

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

        # 다음 이미지 번호
        self.next_image_number = self.ssh.get_next_image_number()
        self.number_label.setText(f"sustube{self.next_image_number}")

        # 등록된 제품 수 + 공정 사진 수
        remote_file = self.ssh.get_remote_gallery_path()
        content, err = self.ssh.read_remote_file(remote_file)
        if content:
            captions = get_all_captions(content)
            self.count_label.setText(f"등록된 제품: {len(captions)}개")

            # 공정 사진 수 계산 (#process 내부 gallery-item 수)
            process_match = re.search(r'<div\s+id="process"[^>]*>.*?<div\s+class="gallery">(.*?)</div>\s*</div>', content, re.DOTALL)
            if process_match:
                process_items = re.findall(r'gallery-item', process_match.group(1))
                self.process_count_label.setText(f"공정 사진: {len(process_items)}개")
            else:
                self.process_count_label.setText("")

            self.log(f"📊 원격 갤러리: {len(captions)}개 제품, 다음 번호: sustube{self.next_image_number}")
        else:
            self.count_label.setText("gallery.html 읽기 실패")
            self.log(f"⚠️ {err}")
            self.log(f"   확인 경로: {remote_file}")

        self.refresh_btn.setEnabled(True)

    def refresh_data(self):
        self.load_remote_info()
        self.refresh_process_folders()

    def _on_process_folder_selected(self, item):
        """공정 폴더 선택 시"""
        self.selected_process_folder = item.text()
        self.process_add_btn.setEnabled(True)
        self.log(f"📁 선택한 폴더: {self.selected_process_folder}")

    def refresh_process_folders(self):
        """로컬 이미지 폴더의 하위 폴더 목록 갱신"""
        self.process_folder_list.clear()
        self.selected_process_folder = None
        self.process_add_btn.setEnabled(False)

        local_dir = self.ssh.settings.get("local_image_dir", "")
        if not local_dir or not os.path.isdir(local_dir):
            self.process_folder_list.addItem("⚠️ 설정에서 로컬 이미지 폴더를 지정해주세요.")
            return

        try:
            dirs = [
                d for d in os.listdir(local_dir)
                if os.path.isdir(os.path.join(local_dir, d))
            ]
            self.process_folders = sorted(dirs)
            if not self.process_folders:
                self.process_folder_list.addItem("⚠️ 하위 폴더가 없습니다.")
                return
            for d in self.process_folders:
                self.process_folder_list.addItem(d)
            self.log(f"📂 로컬 이미지 폴더: {len(self.process_folders)}개 하위 폴더 발견")
        except Exception as e:
            self.process_folder_list.addItem(f"⚠️ 폴더 읽기 실패: {e}")
            self.log(f"⚠️ 폴더 읽기 오류: {e}")

    def add_process_photos(self):
        """선택한 공정 폴더의 사진을 갤러리에 추가"""
        if not self.ssh.is_connected():
            QMessageBox.warning(self, "연결 필요", "먼저 라즈베리파이에 연결해주세요.")
            return

        folder = self.selected_process_folder
        if not folder:
            QMessageBox.warning(self, "선택 필요", "공정 사진 폴더를 선택해주세요.")
            return

        local_dir = self.ssh.settings.get("local_image_dir", "")
        folder_path = os.path.join(local_dir, folder)
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "폴더 없음", f"로컬 폴더를 찾을 수 없습니다:\n{folder_path}")
            return

        # 폴더 내 이미지 파일 수집
        image_files = sorted([
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if is_supported_image(f)
        ])
        if not image_files:
            QMessageBox.warning(self, "이미지 없음", f"'{folder}' 폴더에 지원하는 이미지 파일이 없습니다.\n(JPG, PNG, BMP, TIFF, WebP)")
            return

        reply = QMessageBox.question(
            self, "공정 사진 추가",
            f"📁 {folder} ({PROCESS_CAPTIONS.get(folder, folder)})\n"
            f"🖼️ {len(image_files)}개 이미지를 업로드합니다.\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 1. 이미지 변환 (WebP)
        self.log(f"🔄 WebP 변환 시작... ({len(image_files)}개, 폴더: {folder})")
        self.process_add_btn.setEnabled(False)
        self.process_add_btn.setText("⏳ 처리중...")

        temp_dir = tempfile.mkdtemp(prefix=f"servo_{folder}_")
        image_numbers = []
        full_upload_paths = []
        thumb_upload_paths = []

        try:
            # 원격에서 다음 번호 확인
            next_num = self.ssh.get_next_process_number(folder)

            for i, img_path in enumerate(image_files):
                base_name = f"{folder}{next_num + i}"
                full_path, thumb_path, error = convert_to_webp(
                    img_path, temp_dir, base_name
                )
                if error:
                    raise Exception(error)

                image_numbers.append(next_num + i)
                full_upload_paths.append(full_path)
                thumb_upload_paths.append(thumb_path)
                self.log(f"  ✅ {base_name}.webp 변환 완료")

            # 2. 이미지 업로드
            self.log("📤 이미지 업로드 중...")
            remote_base = self.ssh.get_remote_process_folder(folder)

            for full_path, thumb_path, num in zip(
                full_upload_paths, thumb_upload_paths, image_numbers
            ):
                remote_full = f"{remote_base}/{folder}{num}.webp"
                ok, msg = self.ssh.upload_file(full_path, remote_full)
                if not ok:
                    raise Exception(msg)

                remote_thumb = f"{remote_base}/thumbs/{folder}{num}_thumb.webp"
                ok, msg = self.ssh.upload_file(thumb_path, remote_thumb)
                if not ok:
                    raise Exception(msg)

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

            # 4. 수정된 HTML 업로드
            ok, msg = self.ssh.write_remote_file(remote_file, modified_html)
            if not ok:
                raise Exception(msg)

            # 5. 완료
            self.log(f"🎉 공정 사진 업데이트 완료!")
            self.log(f"   폴더: {folder}")
            self.log(f"   이미지: {', '.join(f'{folder}{n}' for n in image_numbers)}")

            QMessageBox.information(
                self, "✅ 완료",
                f"⚙️ 공정 사진 추가 완료!\n\n"
                f"폴더: {folder}\n"
                f"이미지: {len(image_numbers)}개\n"
                f"파일: {', '.join(f'{folder}{n}.webp' for n in image_numbers)}"
            )

        except Exception as e:
            self.log(f"❌ 오류 발생: {e}")
            QMessageBox.critical(self, "오류", f"작업 중 오류가 발생했습니다.\n\n{e}")
        finally:
            # temp_dir 정리
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.process_add_btn.setEnabled(True)
            self.process_add_btn.setText("⚙️ 공정 사진 추가")
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
        self.add_btn.setEnabled(False)
        self.add_btn.setText("⏳ 처리중...")

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
            self.add_btn.setEnabled(True)
            self.add_btn.setText("✅ 갤러리에 추가")
