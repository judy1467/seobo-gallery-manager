"""SSH/SFTP 클라이언트 - 라즈베리파이 연결 및 파일 전송"""

import os
import re
import json
import paramiko
from typing import Optional, Dict, List, Tuple

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_SETTINGS = {
    "host": "",
    "port": 22,
    "username": "",
    "password": "",
    "use_key": False,
    "key_path": "",
    "pi_image_dir": "",
    "remote_path": "/var/www/html",
    "gallery_file": "gallery.html",
}


def load_settings() -> Dict:
    """SSH 설정을 JSON에서 불러온다. (이전 키 자동 마이그레이션)"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 이전 버전 호환: local_image_dir → pi_image_dir
            if "local_image_dir" in raw and "pi_image_dir" not in raw:
                raw["pi_image_dir"] = raw.pop("local_image_dir")
            return {**DEFAULT_SETTINGS, **raw}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: Dict):
    """SSH 설정을 JSON에 저장한다."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


class SSHClient:
    """라즈베리파이 SSH/SFTP 연결 관리"""

    def __init__(self):
        self.settings = load_settings()
        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

    def is_connected(self) -> bool:
        return self._ssh is not None and self._ssh.get_transport() is not None and self._ssh.get_transport().is_active()

    def connect(self) -> Tuple[bool, str]:
        """SSH 연결. (성공여부, 메시지) 반환"""
        try:
            if self.is_connected():
                return True, "이미 연결되어 있습니다."

            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.settings["host"],
                "port": int(self.settings.get("port", 22)),
                "username": self.settings["username"],
                "timeout": 10,
            }

            auth_mode = "key" if self.settings.get("use_key") else "password"

            if auth_mode == "key":
                key_path = self.settings.get("key_path", "")
                # key_path가 없으면 기본 키(~/.ssh/id_rsa 등) 자동 탐색
                if not key_path:
                    key_path = os.path.expanduser("~/.ssh/id_rsa")
                if os.path.exists(key_path):
                    try:
                        pkey = paramiko.RSAKey.from_private_key_file(key_path)
                    except paramiko.SSHException:
                        try:
                            pkey = paramiko.Ed25519Key.from_private_key_file(key_path)
                        except paramiko.SSHException:
                            pkey = paramiko.ECDSAKey.from_private_key_file(key_path)
                    connect_kwargs["pkey"] = pkey
                else:
                    return False, f"❌ 키 파일을 찾을 수 없음: {key_path}"
            else:
                connect_kwargs["password"] = self.settings["password"]

            self._ssh.connect(**connect_kwargs)
            self._sftp = self._ssh.open_sftp()
            auth_label = "키" if auth_mode == "key" else "비밀번호"
            return True, f"✅ {auth_label} 인증 연결 성공: {self.settings['username']}@{self.settings['host']}"
        except Exception as e:
            self._ssh = None
            self._sftp = None
            return False, f"❌ 연결 실패: {str(e)}"

    def disconnect(self):
        """연결 종료"""
        try:
            if self._sftp:
                self._sftp.close()
            if self._ssh:
                self._ssh.close()
        except Exception:
            pass
        finally:
            self._sftp = None
            self._ssh = None

    def exec_command(self, command: str) -> Tuple[bool, str]:
        """원격 명령 실행"""
        if not self.is_connected():
            return False, "연결되지 않았습니다."
        try:
            _, stdout, stderr = self._ssh.exec_command(command, timeout=30)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                return False, err
            return True, out
        except Exception as e:
            return False, str(e)

    def read_remote_file(self, remote_path: str) -> Tuple[Optional[str], str]:
        """원격 파일을 읽어 문자열로 반환. (내용|None, 에러메시지)"""
        if not self._sftp:
            return None, "SFTP 연결 없음"
        try:
            # 파일 존재 확인
            self._sftp.stat(remote_path)
        except FileNotFoundError:
            return None, f"파일 없음: {remote_path}"
        except Exception as e:
            return None, f"파일 접근 오류 ({remote_path}): {str(e)}"
        try:
            with self._sftp.open(remote_path, "r") as f:
                content = f.read()
            # bytes면 문자열로 디코딩
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            return content, ""
        except Exception as e:
            return None, f"파일 읽기 오류 ({remote_path}): {str(e)}"

    def write_remote_file(self, remote_path: str, content: str) -> Tuple[bool, str]:
        """원격 파일에 문자열 쓰기"""
        if not self._sftp:
            return False, "SFTP 연결 없음"
        try:
            with self._sftp.open(remote_path, "w") as f:
                f.write(content.encode("utf-8") if isinstance(content, str) else content)
            return True, "파일 저장 완료"
        except Exception as e:
            return False, f"파일 쓰기 실패: {str(e)}"

    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """로컬 파일을 원격으로 업로드"""
        if not self._sftp:
            return False, "SFTP 연결 없음"
        try:
            # 디렉토리 생성
            remote_dir = os.path.dirname(remote_path)
            self._ensure_remote_dir(remote_dir)
            self._sftp.put(local_path, remote_path)
            return True, f"업로드 완료: {os.path.basename(local_path)}"
        except Exception as e:
            return False, f"업로드 실패: {str(e)}"

    def _ensure_remote_dir(self, remote_dir: str):
        """원격 디렉토리가 없으면 생성"""
        try:
            self._sftp.stat(remote_dir)
        except FileNotFoundError:
            parts = remote_dir.strip("/").split("/")
            path = ""
            for part in parts:
                path = f"{path}/{part}" if path else f"/{part}"
                try:
                    self._sftp.stat(path)
                except FileNotFoundError:
                    self._sftp.mkdir(path)

    def list_remote_directories(self, remote_dir: str) -> Tuple[bool, List[str]]:
        """원격 디렉토리 내 하위 폴더 목록 반환"""
        cmd = f'find {remote_dir} -maxdepth 1 -type d ! -path "{remote_dir}" -printf "%f\\n" 2>/dev/null | sort'
        success, output = self.exec_command(cmd)
        if not success:
            # fallback: ls로 시도
            cmd = f'ls -d {remote_dir}/*/ 2>/dev/null | xargs -I{{}} basename {{}}'
            success, output = self.exec_command(cmd)
        if success and output.strip():
            return True, [d.strip() for d in output.split("\n") if d.strip()]
        return True, []

    def get_next_image_number(self) -> int:
        """원격 서버에서 다음 sustube 이미지 번호를 찾는다."""
        # 1) sustube*.webp 파일을 ls로 정렬하여 가장 큰 번호 찾기
        cmd = (
            f'ls {self.settings["remote_path"]}/images/sustube/sustube*.webp '
            f'2>/dev/null | sed "s/.*sustube//;s/\\.webp//" | sort -n | tail -1'
        )
        success, output = self.exec_command(cmd)
        if success and output.strip():
            try:
                return int(output.strip()) + 1
            except ValueError:
                pass

        # 2) fallback: find로 sustube*.webp 파일 개수 확인 후 번호 추정
        success, output = self.exec_command(
            f'find {self.settings["remote_path"]}/images/sustube/ '
            f'-name "sustube*.webp" 2>/dev/null | sort -t"e" -k2 -n | tail -1 '
            f'| sed "s/.*sustube//;s/\\.webp//"'
        )
        if success and output.strip():
            try:
                return int(output.strip()) + 1
            except ValueError:
                pass

        # 3) 파일이 전혀 없으면 1부터 시작
        return 1

    def get_next_process_number(self, folder_name: str) -> int:
        """원격 서버에서 특정 공정 폴더의 다음 이미지 번호를 찾는다."""
        prefix = folder_name
        remote_dir = f'{self.settings["remote_path"]}/images/{folder_name}'

        # 1) {prefix}*.webp 파일을 ls로 정렬
        cmd = (
            f'ls {remote_dir}/{prefix}*.webp '
            f'2>/dev/null | sed "s/.*{prefix}//;s/\\.webp//" | sort -n | tail -1'
        )
        success, output = self.exec_command(cmd)
        if success and output.strip():
            try:
                return int(output.strip()) + 1
            except ValueError:
                pass

        # 2) fallback: find 사용
        success, output = self.exec_command(
            f'find {remote_dir}/ '
            f'-name "{prefix}*.webp" 2>/dev/null '
            f'| sed "s/.*{prefix}//;s/\\.webp//" | sort -n | tail -1'
        )
        if success and output.strip():
            try:
                return int(output.strip()) + 1
            except ValueError:
                pass

        # 3) 파일 없으면 1부터
        return 1

    def get_remote_process_folder(self, folder_name: str) -> str:
        """공정 사진 폴더의 원격 경로"""
        return f'{self.settings["remote_path"]}/images/{folder_name}'

    def get_remote_gallery_path(self) -> str:
        """gallery.html의 전체 원격 경로"""
        return f'{self.settings["remote_path"]}/{self.settings["gallery_file"]}'
