#!/usr/bin/env python3
"""Upload the contents of Uploads to an FTP server and remove successful uploads."""

from __future__ import annotations

import configparser
import logging
import shutil
import sys
from ftplib import FTP, FTP_TLS, all_errors
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "upload.config"
FTP_EXCEPTIONS = (OSError, *all_errors)


class SessionReuseFTP_TLS(FTP_TLS):
    """FTP over TLS client that reuses the control-channel TLS session."""

    def ntransfercmd(self, cmd, rest=None):
        conn, size = FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn,
                server_hostname=self.host,
                session=self.sock.session,
            )
        return conn, size


def load_config() -> tuple[configparser.ConfigParser, Path, Path, Path]:
    config = configparser.ConfigParser()
    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(f"No se encuentra el fichero de configuración: {CONFIG_FILE}")

    config.read(CONFIG_FILE, encoding="utf-8")
    if not config.has_section("ftp"):
        raise ValueError("El fichero de configuración debe contener la sección [ftp]")

    for option in ("host", "username", "password"):
        if not config.get("ftp", option, fallback="").strip():
            raise ValueError(f"Falta el valor ftp.{option} en {CONFIG_FILE}")

    upload_dir = Path(config.get("paths", "upload_dir", fallback="Uploads"))
    if not upload_dir.is_absolute():
        upload_dir = SCRIPT_DIR / upload_dir

    log_file = Path(config.get("paths", "log_file", fallback="upload.log"))
    if not log_file.is_absolute():
        log_file = SCRIPT_DIR / log_file

    completed_dir = Path(config.get("paths", "completed_dir", fallback="Completed"))
    if not completed_dir.is_absolute():
        completed_dir = SCRIPT_DIR / completed_dir

    return config, upload_dir, log_file, completed_dir


def configure_logging(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
        encoding="utf-8",
    )


def ensure_remote_directory(
    ftp: FTP,
    base_directory: str,
    relative_directory: Path,
) -> None:
    """Create a remote directory and all its missing parents."""
    ftp.cwd(base_directory)
    for directory in relative_directory.parts:
        if directory in ("", "."):
            continue
        try:
            ftp.cwd(directory)
        except FTP_EXCEPTIONS:
            ftp.mkd(directory)
            ftp.cwd(directory)


def remote_directory(ftp: FTP, base_directory: str, relative_path: Path) -> None:
    """Create and enter the directory containing a relative file path."""
    ensure_remote_directory(ftp, base_directory, relative_path.parent)


def upload_files(
    config: configparser.ConfigParser,
    upload_dir: Path,
    completed_dir: Path,
) -> int:
    files = sorted(
        path
        for path in upload_dir.rglob("*")
        if path.is_file() and path.name != ".gitkeep"
    )
    directories = sorted(path for path in upload_dir.rglob("*") if path.is_dir())
    if not files and not directories:
        logging.info("No hay ficheros para subir en %s", upload_dir)
        return 0

    host = config.get("ftp", "host").strip()
    port = config.getint("ftp", "port", fallback=21)
    username = config.get("ftp", "username").strip()
    password = config.get("ftp", "password")
    remote_dir = config.get("ftp", "remote_dir", fallback="/").strip() or "/"
    timeout = config.getfloat("ftp", "timeout", fallback=30.0)
    use_tls = config.getboolean("ftp", "tls", fallback=True)
    failures = 0

    try:
        ftp_class = SessionReuseFTP_TLS if use_tls else FTP
        with ftp_class() as ftp:
            ftp.connect(host=host, port=port, timeout=timeout)
            ftp.login(user=username, passwd=password)
            if use_tls:
                ftp.prot_p()
            ftp.set_pasv(True)

            for directory in directories:
                relative_directory = directory.relative_to(upload_dir)
                try:
                    ensure_remote_directory(ftp, remote_dir, relative_directory)
                    logging.info("DIRECTORIO | %s | creado o ya existente", relative_directory)
                except FTP_EXCEPTIONS as error:
                    failures += 1
                    logging.error("FALLO | directorio %s | %s", relative_directory, error)

            for file_path in files:
                relative_path = file_path.relative_to(upload_dir)
                try:
                    remote_directory(ftp, remote_dir, relative_path)
                    with file_path.open("rb") as file_handle:
                        ftp.storbinary(f"STOR {relative_path.name}", file_handle)
                except FTP_EXCEPTIONS as error:
                    failures += 1
                    logging.error("FALLO | %s | %s", relative_path, error)
                    continue

                try:
                    completed_path = completed_dir / relative_path
                    completed_path.parent.mkdir(parents=True, exist_ok=True)
                    if completed_path.exists():
                        raise FileExistsError(f"El destino ya existe: {completed_path}")
                    shutil.move(str(file_path), str(completed_path))
                    logging.info("ÉXITO | %s | movido a %s", relative_path, completed_path)
                except OSError as error:
                    failures += 1
                    logging.error(
                        "SUBIDA OK, FALLO AL MOVER | %s | %s",
                        relative_path,
                        error,
                    )
    except FTP_EXCEPTIONS as error:
        failures = len(files)
        logging.error("FALLO DE CONEXIÓN | %s | %s", host, error)
        for file_path in files:
            logging.error(
                "FALLO | %s | no se pudo conectar al servidor",
                file_path.relative_to(upload_dir),
            )

    return failures


def main() -> int:
    try:
        config, upload_dir, log_file, completed_dir = load_config()
        configure_logging(log_file)
        if not upload_dir.is_dir():
            raise NotADirectoryError(f"No se encuentra la carpeta de subida: {upload_dir}")
        failures = upload_files(config, upload_dir, completed_dir)
    except (FileNotFoundError, NotADirectoryError, ValueError, configparser.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if failures:
        print(f"Proceso terminado con {failures} fichero(s) fallido(s).", file=sys.stderr)
        return 1
    print("Proceso terminado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
