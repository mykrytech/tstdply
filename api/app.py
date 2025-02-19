import os
import tempfile
from flask import Flask, request, render_template, send_file, redirect, url_for, flash
import yt_dlp
from flask_socketio import SocketIO

# Atur path untuk folder templates (folder templates berada di level atas folder api)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
template_folder = os.path.join(base_dir, "templates")

app = Flask(__name__, template_folder=template_folder)
app.secret_key = "secret_keyhere"  # Ganti dengan secret key yang aman
socketio = SocketIO(app)

# Tentukan path ke binary ffmpeg yang sudah dibundling
ffmpeg_path = os.path.join(base_dir, "ffmpeg", "ffmpeg")

def progress_hook(d):
    if d['status'] == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes', d.get('total_bytes_estimate'))
        if total:
            percent = downloaded / total * 100
            print(f"Download progress: {percent:.2f}%")
            socketio.emit('download_progress', {'percent': percent})
    elif d['status'] == 'finished':
        print("Unduhan selesai, memproses file...")
        socketio.emit('download_progress', {'percent': 100, 'message': 'Audio berhasil diunduh'})

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        youtube_url = request.form.get("youtube_url")
        if not youtube_url:
            flash("Masukkan URL YouTube yang valid!")
            return redirect(url_for("index"))
        try:
            # Membuat temporary directory untuk menyimpan file hasil download
            temp_dir = tempfile.mkdtemp()
            # Template output: nama file akan disesuaikan dengan judul video dan ekstensi yang sesuai
            output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': ffmpeg_path,  # Gunakan path ffmpeg yang sudah dibundling
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=True)
                title = info_dict.get('title', 'audio')

            # Bersihkan nama file jika mengandung karakter tidak valid
            safe_title = "".join([c if c.isalnum() or c in " ._-()" else "_" for c in title])
            safe_filename = f"{safe_title}.mp3"
            safe_filepath = os.path.join(temp_dir, safe_filename)

            # Jika file tidak ditemukan dengan nama yang diharapkan, cari file mp3 yang ada
            if not os.path.exists(safe_filepath):
                for file in os.listdir(temp_dir):
                    if file.endswith(".mp3"):
                        safe_filepath = os.path.join(temp_dir, file)
                        break

            if not os.path.exists(safe_filepath):
                flash("Gagal menemukan file MP3 hasil download.")
                return redirect(url_for("index"))

            # Mengirim file MP3 sebagai attachment ke pengguna
            response = send_file(
                safe_filepath,
                as_attachment=True,
                download_name=safe_filename
            )

            # Menghapus file temporary setelah file dikirim
            response.call_on_close(lambda: os.remove(safe_filepath))
            return response

        except Exception as e:
            flash("Terjadi kesalahan: " + str(e))
            return redirect(url_for("index"))
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)
