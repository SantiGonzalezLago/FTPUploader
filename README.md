# FTPUploader

Script para subir por **FTP** los ficheros de `Uploads` y moverlos a
`Completed` cuando la transferencia termina correctamente.

## Requisitos

- Python 3.9 o posterior.
- Acceso a un servidor FTP.

El script utiliza `ftplib`, incluida en la biblioteca estándar de Python, por
lo que no necesita instalar dependencias adicionales. Con `tls=true` utiliza
FTP sobre TLS (FTPS), necesario cuando el servidor exige cifrado para el
inicio de sesión.

## Configuración

Copia el ejemplo y edita los valores:

```bash
cp upload.config.example upload.config
```

El fichero `upload.config` debe tener esta estructura:

```ini
[ftp]
host=ftp.ejemplo.com
port=21
username=usuario_ftp
password=pon_aqui_la_contraseña
tls=true
remote_dir=/
timeout=30

[paths]
upload_dir=Uploads
completed_dir=Completed
log_file=upload.log
```

Las rutas relativas se interpretan respecto al directorio del script. No
subas `upload.config` a ningún repositorio: contiene la contraseña.

## Uso

Coloca los ficheros que quieras transferir dentro de `Uploads` y ejecuta:

```bash
python3 upload.py
```

El script:

1. Se conecta al servidor FTP en modo pasivo.
2. Recorre `Uploads`, incluyendo sus subdirectorios y carpetas vacías.
3. Crea en el servidor todas las carpetas, incluidas las que no contienen
   ficheros.
4. Registra cada intento en `upload.log` con fecha, hora y resultado.
5. Mueve cada fichero a `Completed` únicamente después de subirlo con éxito.

La estructura de subcarpetas se conserva dentro de `Completed`. Si el fichero
de destino ya existe, el original no se sobrescribe y se registra el fallo.

El `.gitignore` solo afecta a Git; no impide que el script lea `Uploads` ni
que cree las carpetas vacías en el servidor FTP.

Git no almacena carpetas vacías. Para conservarlas en el repositorio se usa
un fichero vacío `.gitkeep` dentro de cada carpeta vacía. Esos ficheros están
permitidos por `.gitignore` y el script los ignora para no subirlos al FTP.

El proceso termina con código `0` si todos los ficheros se han subido
correctamente y con código `1` si se produce algún error.
