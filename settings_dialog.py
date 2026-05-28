"""SSH 설정 다이얼로그"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel,
    QMessageBox, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from ssh_client import load_settings, save_settings


class SettingsDialog(QDialog):
    """SSH 연결 정보 설정 다이얼로그"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔌 라즈베리파이 연결 설정")
        self.setMinimumWidth(450)
        self.setModal(True)

        self.settings = load_settings()
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("예: 192.168.0.100")
        form.addRow("호스트 IP:", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(22)
        form.addRow("포트:", self.port_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("예: pi")
        form.addRow("사용자명:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("SSH 비밀번호")
        form.addRow("비밀번호:", self.password_input)

        self.remote_path_input = QLineEdit()
        self.remote_path_input.setPlaceholderText("예: /var/www/html")
        form.addRow("원격 경로:", self.remote_path_input)

        self.gallery_file_input = QLineEdit()
        self.gallery_file_input.setPlaceholderText("예: gallery.html")
        form.addRow("갤러리 파일명:", self.gallery_file_input)

        layout.addLayout(form)

        # 버튼
        btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("🔍 연결 테스트")
        self.test_btn.clicked.connect(self.test_connection)
        btn_layout.addWidget(self.test_btn)
        btn_layout.addStretch()

        self.save_btn = QPushButton("💾 저장")
        self.save_btn.clicked.connect(self.save_and_close)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _load_values(self):
        self.host_input.setText(self.settings.get("host", ""))
        self.port_input.setValue(int(self.settings.get("port", 22)))
        self.username_input.setText(self.settings.get("username", ""))
        self.password_input.setText(self.settings.get("password", ""))
        self.remote_path_input.setText(self.settings.get("remote_path", "/var/www/html"))
        self.gallery_file_input.setText(self.settings.get("gallery_file", "gallery.html"))

    def get_settings(self) -> dict:
        return {
            "host": self.host_input.text().strip(),
            "port": self.port_input.value(),
            "username": self.username_input.text().strip(),
            "password": self.password_input.text().strip(),
            "remote_path": self.remote_path_input.text().strip(),
            "gallery_file": self.gallery_file_input.text().strip(),
        }

    def test_connection(self):
        """설정값으로 SSH 연결 테스트"""
        from ssh_client import SSHClient

        test_client = SSHClient()
        test_client.settings = self.get_settings()
        success, msg = test_client.connect()
        test_client.disconnect()

        if success:
            QMessageBox.information(self, "연결 테스트", msg)
        else:
            QMessageBox.warning(self, "연결 테스트", msg)

    def save_and_close(self):
        settings = self.get_settings()
        if not settings["host"]:
            QMessageBox.warning(self, "입력 확인", "호스트 IP를 입력해주세요.")
            return
        if not settings["username"]:
            QMessageBox.warning(self, "입력 확인", "사용자명을 입력해주세요.")
            return
        save_settings(settings)
        self.accept()
