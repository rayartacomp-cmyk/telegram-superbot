#!/usr/bin/env python3
"""
TELEGRAM SUPER BOT - 100% GRATIS
Fitur: Film Streaming, Musik, Video Download, Drama, Anime
"""

import telebot
from telebot import types
import requests
import json
import os
import sqlite3
import threading
import yt_dlp
from youtube_search import YoutubeSearch
import lyricsgenius
import random
import re
import time
from datetime import datetime
import urllib.parse
import cloudscraper
from bs4 import BeautifulSoup
import hashlib

# ============ KONFIGURASI ============
print("🚀 Starting Telegram SuperBot...")

# Token dari @BotFather
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
TMDB_API_KEY = os.getenv('TMDB_API_KEY', 'YOUR_TMDB_API_KEY')
GENIUS_TOKEN = os.getenv('GENIUS_TOKEN', 'YOUR_GENIUS_TOKEN')

# Inisialisasi bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML', num_threads=10)

# Inisialisasi Genius
try:
    genius = lyricsgenius.Genius(GENIUS_TOKEN)
    genius.verbose = False
    genius.remove_section_headers = True
except:
    print("⚠️ Genius API tidak terinisialisasi. Fitur lyrics mungkin tidak berfungsi.")

# ============ DATABASE ============
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect('superbot.db')
    c = conn.cursor()
    
    # Tabel users
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabel downloads
    c.execute('''CREATE TABLE IF NOT EXISTS downloads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  content_type TEXT,
                  title TEXT,
                  download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Tabel watch_history
    c.execute('''CREATE TABLE IF NOT EXISTS watch_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  title TEXT,
                  content_type TEXT,
                  watch_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

init_database()

# ============ FUNGSI BANTUAN ============
def log_user_action(user_id, action, details=""):
    """Log user actions to database"""
    try:
        conn = sqlite3.connect('superbot.db')
        c = conn.cursor()
        
        # Insert or update user
        c.execute('''INSERT OR IGNORE INTO users (user_id) VALUES (?)''', (user_id,))
        
        conn.commit()
        conn.close()
    except:
        pass

def create_directories():
    """Create necessary directories"""
    dirs = ['downloads', 'downloads/music', 'downloads/video', 'downloads/temp', 'cache']
    for dir_name in dirs:
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            print(f"📁 Created directory: {dir_name}")

create_directories()

# ============ FITUR 1: JOKES ============
class JokeManager:
    def __init__(self):
        self.categories = ['Programming', 'Dark', 'Pun', 'Spooky', 'Christmas', 'Misc']
    
    def get_joke(self, category='Any'):
        """Get joke from JokeAPI"""
        try:
            if category == 'random' or category == 'Any':
                url = "https://v2.jokeapi.dev/joke/Any?type=single"
            else:
                url = f"https://v2.jokeapi.dev/joke/{category}?type=single"
            
            response = requests.get(url, timeout=10).json()
            
            if response.get('joke'):
                return response['joke']
            elif response.get('setup'):
                return f"{response['setup']}\n\n{response['delivery']}"
            else:
                return "🤣 Kenapa programmer selalu pakai kacamata? Karena mereka tidak bisa C#!"
        except:
            # Fallback jokes
            fallback_jokes = [
                "Kenapa komputer tidak pernah lapar? Karena sudah ada byte-byte!",
                "Apa bedanya programmer dan politisi? Programmer hanya membuat bug, politisi membuat janji bug!",
                "Kenapa JavaScript developer pusing? Karena terlalu banyak callback!",
                "Apa makanan favorit programmer? Cookies!",
                "Kenapa programmer tidak pernah mandi? Karena mereka takut bug!"
            ]
            return random.choice(fallback_jokes)

joke_manager = JokeManager()

@bot.message_handler(commands=['joke', 'jokes'])
def send_joke(message):
    """Send joke command"""
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    # Add joke categories
    buttons = []
    for category in joke_manager.categories:
        buttons.append(types.InlineKeyboardButton(
            category, 
            callback_data=f'joke_{category.lower()}'
        ))
    
    # Add rows
    for i in range(0, len(buttons), 3):
        keyboard.add(*buttons[i:i+3])
    
    keyboard.add(types.InlineKeyboardButton("🎲 Random Joke", callback_data='joke_random'))
    
    bot.send_message(
        message.chat.id,
        "🤣 <b>PILIH KATEGORI JOKE:</b>\n\nPilih kategori atau random:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('joke_'))
def joke_callback(call):
    """Handle joke category selection"""
    category = call.data.replace('joke_', '')
    joke = joke_manager.get_joke(category)
    
    # Create keyboard with back button
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔄 Joke Lain", callback_data='back_to_jokes'))
    
    bot.edit_message_text(
        f"🎭 <b>Joke {category.capitalize()}:</b>\n\n{joke}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )

# ============ FITUR 2: MUSIC PLAYER ============
class MusicPlayer:
    def __init__(self):
        print("🎵 Music Player initialized")
    
    def search_youtube(self, query, limit=10):
        """Search music on YouTube"""
        try:
            results = YoutubeSearch(query, max_results=limit).to_dict()
            formatted = []
            
            for result in results:
                # Clean title
                title = result['title']
                if ' - ' in title:
                    artist, song = title.split(' - ', 1)
                else:
                    artist = result['channel']
                    song = title
                
                formatted.append({
                    'id': result['id'],
                    'title': title,
                    'artist': artist,
                    'song': song,
                    'duration': result['duration'],
                    'thumbnail': f"https://i.ytimg.com/vi/{result['id']}/hqdefault.jpg",
                    'url': f"https://youtube.com/watch?v={result['id']}"
                })
            
            return formatted
        except Exception as e:
            print(f"❌ YouTube search error: {e}")
            return []
    
    def search_youtube_music(self, query, limit=10):
        """Search on YouTube Music"""
        # YouTube Music search is same as YouTube
        return self.search_youtube(f"{query} official audio", limit)
    
    def download_audio(self, video_id, quality='192'):
        """Download audio from YouTube"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality,
                }],
                'outtmpl': 'downloads/music/%(title)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'extract_audio': True,
                'audio_format': 'mp3',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
                
                if os.path.exists(filename):
                    return filename, info['title']
            
            return None, None
        except Exception as e:
            print(f"❌ Download error: {e}")
            return None, None

music_player = MusicPlayer()

@bot.message_handler(commands=['music', 'play', 'lagu'])
def music_command(message):
    """Music command handler"""
    # Check if query is provided
    if len(message.text.split()) > 1:
        query = message.text.split(' ', 1)[1]
        search_music(message, query)
    else:
        # Show music source selection
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("🎵 YouTube", callback_data="music_youtube"),
            types.InlineKeyboardButton("🎶 YouTube Music", callback_data="music_ytmusic")
        )
        
        bot.send_message(
            message.chat.id,
            "🎵 <b>PILIH SUMBER MUSIK:</b>\n\n"
            "• <b>YouTube</b>: Semua lagu tersedia\n"
            "• <b>YouTube Music</b>: Kualitas audio terbaik\n\n"
            "🔥 <i>Kirim /music [judul lagu] untuk langsung search</i>",
            reply_markup=keyboard
        )

def search_music(message, query=None):
    """Search music"""
    if not query:
        msg = bot.send_message(message.chat.id, "🎵 <b>Kirim judul lagu atau artis:</b>")
        bot.register_next_step_handler(msg, process_music_search)
        return
    
    process_music_search(message, query)

def process_music_search(message, query=None):
    """Process music search"""
    if not query:
        query = message.text
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Search on YouTube
    results = music_player.search_youtube(query, limit=8)
    
    if not results:
        bot.reply_to(message, "❌ Tidak ditemukan hasil. Coba kata kunci lain.")
        return
    
    # Create results keyboard
    keyboard = types.InlineKeyboardMarkup()
    
    for i, track in enumerate(results[:8]):
        title_display = f"{track['song'][:30]}..." if len(track['song']) > 30 else track['song']
        btn_text = f"{i+1}. {title_display} ({track['duration']})"
        
        callback_data = f"playmusic_{track['id']}_{hashlib.md5(track['title'].encode()).hexdigest()[:8]}"
        keyboard.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    bot.reply_to(
        message,
        f"🎵 <b>HASIL PENCARIAN:</b>\n\n"
        f"Kata kunci: <code>{query}</code>\n"
        f"Ditemukan: <b>{len(results)}</b> hasil\n\n"
        f"Pilih lagu:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('playmusic_'))
def play_music_callback(call):
    """Handle music play callback"""
    data = call.data.replace('playmusic_', '')
    video_id = data.split('_')[0]
    
    # Update message
    bot.edit_message_text(
        "⏬ <b>Mengunduh audio... Mohon tunggu!</b>",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Download in background thread
    def download_and_send():
        try:
            # Download audio
            filename, title = music_player.download_audio(video_id)
            
            if filename and os.path.exists(filename):
                # Send audio file
                with open(filename, 'rb') as audio_file:
                    bot.send_audio(
                        call.message.chat.id,
                        audio_file,
                        title=title[:64] if title else "Unknown",
                        performer="Telegram SuperBot",
                        timeout=60
                    )
                
                # Update message
                bot.edit_message_text(
                    f"✅ <b>Audio berhasil dikirim!</b>\n\n"
                    f"Judul: {title}\n"
                    f"Format: MP3 192kbps",
                    call.message.chat.id,
                    call.message.message_id
                )
                
                # Clean up file
                try:
                    os.remove(filename)
                except:
                    pass
            else:
                bot.edit_message_text(
                    "❌ Gagal mengunduh audio. Coba lagi nanti.",
                    call.message.chat.id,
                    call.message.message_id
                )
        
        except Exception as e:
            bot.edit_message_text(
                f"❌ Error: {str(e)[:100]}",
                call.message.chat.id,
                call.message.message_id
            )
    
    # Start download thread
    threading.Thread(target=download_and_send).start()

# ============ FITUR 3: FILM STREAMING ============
class MovieStreamer:
    def __init__(self):
        self.tmdb_api_key = TMDB_API_KEY
    
    def search_movies(self, query):
        """Search movies from TMDB"""
        try:
            url = f"https://api.themoviedb.org/3/search/movie"
            params = {
                'api_key': self.tmdb_api_key,
                'query': query,
                'language': 'id-ID',
                'page': 1
            }
            
            response = requests.get(url, params=params, timeout=10).json()
            results = []
            
            for movie in response.get('results', [])[:8]:
                # Get poster URL
                poster = None
                if movie.get('poster_path'):
                    poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
                
                results.append({
                    'id': movie['id'],
                    'title': movie['title'],
                    'year': movie.get('release_date', '')[:4] if movie.get('release_date') else 'N/A',
                    'rating': round(movie.get('vote_average', 0), 1),
                    'overview': movie.get('overview', 'Tidak ada sinopsis'),
                    'poster': poster
                })
            
            return results
        except Exception as e:
            print(f"❌ TMDB search error: {e}")
            return []
    
    def get_movie_details(self, movie_id):
        """Get movie details with streaming links"""
        try:
            # Get movie details
            url = f"https://api.themoviedb.org/3/movie/{movie_id}"
            params = {
                'api_key': self.tmdb_api_key,
                'append_to_response': 'videos',
                'language': 'id-ID'
            }
            
            response = requests.get(url, params=params, timeout=10).json()
            
            # Get streaming links from Indonesian sites
            streaming_sites = self.get_indonesian_streaming_sites(response['title'])
            
            return {
                'title': response['title'],
                'year': response.get('release_date', '')[:4] if response.get('release_date') else '',
                'rating': response.get('vote_average', 0),
                'overview': response.get('overview', ''),
                'runtime': response.get('runtime', 0),
                'poster': f"https://image.tmdb.org/t/p/w500{response['poster_path']}" if response.get('poster_path') else None,
                'streaming_sites': streaming_sites,
                'trailer': self.get_trailer(response.get('videos', {}).get('results', []))
            }
        except Exception as e:
            print(f"❌ Get movie details error: {e}")
            return None
    
    def get_indonesian_streaming_sites(self, movie_title):
        """Generate streaming links for Indonesian sites"""
        encoded_title = urllib.parse.quote(movie_title)
        
        sites = [
            {
                'name': '🎬 LK21',
                'url': f"https://layarkaca21.vip/?s={encoded_title}",
                'quality': 'HD',
                'subtitle': 'Indonesia'
            },
            {
                'name': '📺 Dutafilm',
                'url': f"https://dutafilm.com/?s={encoded_title}",
                'quality': 'HD',
                'subtitle': 'Indonesia'
            },
            {
                'name': '🍿 Indoxxi',
                'url': f"https://indoxxi.fun/?s={encoded_title}",
                'quality': 'HD',
                'subtitle': 'Indonesia'
            },
            {
                'name': '🎥 BioskopKeren',
                'url': f"https://bioskopkeren.cloud/search/{encoded_title}",
                'quality': 'HD',
                'subtitle': 'Indonesia'
            },
            {
                'name': '🔍 Google',
                'url': f"https://www.google.com/search?q={encoded_title}+nonton+online+free",
                'quality': 'Multiple',
                'subtitle': 'Various'
            }
        ]
        
        return sites
    
    def get_trailer(self, videos):
        """Get YouTube trailer URL"""
        for video in videos:
            if video['site'] == 'YouTube' and video['type'] == 'Trailer':
                return f"https://youtube.com/watch?v={video['key']}"
        return None

movie_streamer = MovieStreamer()

@bot.message_handler(commands=['movie', 'film', 'movies'])
def movie_command(message):
    """Movie command handler"""
    if len(message.text.split()) > 1:
        query = message.text.split(' ', 1)[1]
        search_movies(message, query)
    else:
        msg = bot.send_message(
            message.chat.id,
            "🎬 <b>CARI FILM:</b>\n\n"
            "Kirim judul film:\n"
            "Contoh: Avengers Endgame, The Batman, John Wick"
        )
        bot.register_next_step_handler(msg, search_movies)

def search_movies(message, query=None):
    """Search movies"""
    if not query:
        query = message.text
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    movies = movie_streamer.search_movies(query)
    
    if not movies:
        bot.reply_to(message, "❌ Film tidak ditemukan. Coba judul lain.")
        return
    
    # Create keyboard with movie options
    keyboard = types.InlineKeyboardMarkup()
    
    for movie in movies[:6]:
        btn_text = f"🎬 {movie['title']} ({movie['year']}) ⭐{movie['rating']}"
        callback_data = f"movie_{movie['id']}"
        keyboard.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    bot.reply_to(
        message,
        f"🎬 <b>HASIL PENCARIAN FILM:</b>\n\n"
        f"Kata kunci: <code>{query}</code>\n"
        f"Ditemukan: <b>{len(movies)}</b> film\n\n"
        f"Pilih film untuk streaming:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('movie_'))
def movie_selected(call):
    """Handle movie selection"""
    movie_id = call.data.replace('movie_', '')
    
    # Get movie details
    movie = movie_streamer.get_movie_details(movie_id)
    
    if not movie:
        bot.answer_callback_query(call.id, "❌ Gagal mengambil data film")
        return
    
    # Create streaming links keyboard
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # Add streaming sites
    for site in movie['streaming_sites']:
        keyboard.add(types.InlineKeyboardButton(
            site['name'],
            url=site['url']
        ))
    
    # Add trailer button if available
    if movie['trailer']:
        keyboard.add(types.InlineKeyboardButton(
            "▶️ Watch Trailer",
            url=movie['trailer']
        ))
    
    # Create message text
    message_text = f"""
🎬 <b>{movie['title']} ({movie['year']})</b>

⭐ Rating: <b>{movie['rating']}/10</b>
⏱ Durasi: <b>{movie['runtime']} menit</b>

<b>📖 Sinopsis:</b>
{movie['overview'][:250]}...

<b>🎯 STREAMING SITES (GRATIS):</b>
• Pilih salah satu situs di bawah
• Semua menyediakan subtitle Indonesia
• Kualitas HD 720p/1080p

<b>⚠️ CATATAN:</b>
<i>Bot ini hanya menyediakan link pencarian ke situs streaming.
Gunakan AdBlock untuk pengalaman lebih baik.</i>
"""
    
    # Send message with poster if available
    try:
        if movie['poster']:
            bot.send_photo(
                call.message.chat.id,
                movie['poster'],
                caption=message_text,
                reply_markup=keyboard
            )
        else:
            bot.send_message(
                call.message.chat.id,
                message_text,
                reply_markup=keyboard
            )
    except:
        bot.send_message(
            call.message.chat.id,
            message_text,
            reply_markup=keyboard
        )

# ============ FITUR 4: VIDEO DOWNLOADER ============
class VideoDownloader:
    def __init__(self):
        print("📥 Video Downloader initialized")
    
    def get_video_info(self, url):
        """Get video information"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                formats = []
                for f in info.get('formats', []):
                    if f.get('ext') in ['mp4', 'webm', '3gp']:
                        formats.append({
                            'format_id': f['format_id'],
                            'ext': f.get('ext', 'mp4'),
                            'quality': f.get('format_note', 'unknown'),
                            'filesize': f.get('filesize', 0),
                            'url': f['url']
                        })
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': formats[:10]  # Limit to 10 formats
                }
        except Exception as e:
            print(f"❌ Get video info error: {e}")
            return None

video_downloader = VideoDownloader()

@bot.message_handler(commands=['video', 'download'])
def video_command(message):
    """Video download command"""
    if len(message.text.split()) > 1:
        url = message.text.split(' ', 1)[1]
        process_video_url(message, url)
    else:
        msg = bot.send_message(
            message.chat.id,
            "📥 <b>DOWNLOAD VIDEO:</b>\n\n"
            "Kirim link YouTube:\n"
            "Contoh: https://youtube.com/watch?v=xxxx"
        )
        bot.register_next_step_handler(msg, process_video_url)

def process_video_url(message, url=None):
    """Process video URL"""
    if not url:
        url = message.text
    
    # Validate URL
    if 'youtube.com' not in url and 'youtu.be' not in url:
        bot.reply_to(message, "❌ Bukan link YouTube yang valid!")
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Get video info
    video_info = video_downloader.get_video_info(url)
    
    if not video_info:
        bot.reply_to(message, "❌ Gagal mengambil info video. Link mungkin tidak valid.")
        return
    
    # Create format selection keyboard
    keyboard = types.InlineKeyboardMarkup()
    
    # Group formats by quality
    quality_groups = {}
    for fmt in video_info['formats']:
        quality = fmt['quality']
        if quality not in quality_groups:
            quality_groups[quality] = []
        quality_groups[quality].append(fmt)
    
    # Add buttons for each quality
    for quality, formats in list(quality_groups.items())[:6]:  # Max 6 qualities
        # Get best format for this quality
        best_format = max(formats, key=lambda x: x['filesize'])
        
        # Format button text
        size_mb = best_format['filesize'] / (1024 * 1024) if best_format['filesize'] else 0
        btn_text = f"📹 {quality.upper()} ({best_format['ext'].upper()}) - {size_mb:.1f}MB"
        
        callback_data = f"dl_{best_format['format_id']}_{hashlib.md5(url.encode()).hexdigest()[:8]}"
        keyboard.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    # Add MP3 audio option
    keyboard.add(types.InlineKeyboardButton(
        "🎵 MP3 Audio (192kbps)",
        callback_data=f"audio_{hashlib.md5(url.encode()).hexdigest()[:8]}"
    ))
    
    # Send video info
    duration_min = video_info['duration'] // 60
    duration_sec = video_info['duration'] % 60
    
    bot.reply_to(
        message,
        f"🎬 <b>{video_info['title']}</b>\n"
        f"⏱ Durasi: {duration_min}:{duration_sec:02d}\n\n"
        f"<b>PILIH FORMAT DOWNLOAD:</b>",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('dl_', 'audio_')))
def download_video_callback(call):
    """Handle video download callback"""
    is_audio = call.data.startswith('audio_')
    
    # Get original message to extract URL
    original_text = call.message.text
    url_match = re.search(r'https?://[^\s]+', original_text)
    
    if not url_match:
        bot.answer_callback_query(call.id, "❌ URL tidak ditemukan")
        return
    
    url = url_match.group(0)
    
    # Update message
    bot.edit_message_text(
        "⏬ <b>Mengunduh... Ini mungkin butuh beberapa menit.</b>",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Download in background thread
    def download_thread():
        try:
            if is_audio:
                # Download audio
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                    'outtmpl': 'downloads/video/%(title)s.%(ext)s',
                    'quiet': True,
                }
            else:
                # Download video
                format_id = call.data.split('_')[1]
                ydl_opts = {
                    'format': format_id,
                    'outtmpl': 'downloads/video/%(title)s.%(ext)s',
                    'quiet': True,
                }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if is_audio:
                    filename = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3')
                
                # Check file size (Telegram limit: 50MB)
                file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                
                if file_size > 45 * 1024 * 1024:  # 45MB limit for safety
                    bot.edit_message_text(
                        "❌ File terlalu besar (>45MB). Telegram batasi 50MB.",
                        call.message.chat.id,
                        call.message.message_id
                    )
                    try:
                        os.remove(filename)
                    except:
                        pass
                    return
                
                # Send file
                if is_audio:
                    with open(filename, 'rb') as f:
                        bot.send_audio(
                            call.message.chat.id,
                            f,
                            title=info['title'][:64],
                            performer="YouTube",
                            timeout=120
                        )
                else:
                    with open(filename, 'rb') as f:
                        bot.send_video(
                            call.message.chat.id,
                            f,
                            caption=f"✅ <b>{info['title']}</b>",
                            timeout=120
                        )
                
                # Update message
                size_mb = file_size / (1024 * 1024)
                bot.edit_message_text(
                    f"✅ <b>Download selesai!</b>\n\n"
                    f"Judul: {info['title']}\n"
                    f"Ukuran: {size_mb:.1f} MB\n"
                    f"Format: {'MP3 Audio' if is_audio else 'Video'}",
                    call.message.chat.id,
                    call.message.message_id
                )
                
                # Clean up
                try:
                    os.remove(filename)
                except:
                    pass
        
        except Exception as e:
            bot.edit_message_text(
                f"❌ Error: {str(e)[:100]}",
                call.message.chat.id,
                call.message.message_id
            )
    
    # Start download thread
    threading.Thread(target=download_thread).start()

# ============ FITUR 5: DRAMA CHINA/KOREA ============
@bot.message_handler(commands=['drama', 'cdrama', 'kdrama'])
def drama_command(message):
    """Drama command handler"""
    if len(message.text.split()) > 1:
        query = message.text.split(' ', 1)[1]
        search_drama(message, query)
    else:
        msg = bot.send_message(
            message.chat.id,
            "📺 <b>CARI DRAMA:</b>\n\n"
            "Kirim judul drama:\n"
            "Contoh: Love O2O, Eternal Love, Crash Landing On You"
        )
        bot.register_next_step_handler(msg, search_drama)

def search_drama(message, query=None):
    """Search drama"""
    if not query:
        query = message.text
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Search drama on popular sites
    encoded_query = urllib.parse.quote(query)
    
    # Drama streaming sites
    drama_sites = [
        {
            'name': '🎎 DramaCool',
            'url': f"https://dramacool.ps/search?keyword={encoded_query}",
            'description': 'Drama Korea & China lengkap'
        },
        {
            'name': '🇰🇷 KissAsian',
            'url': f"https://kissasian.mx/search?q={encoded_query}",
            'description': 'Drama Korea terbaru'
        },
        {
            'name': '🇨🇳 DramaChina',
            'url': f"https://dramachina.biz/?s={encoded_query}",
            'description': 'Drama China populer'
        },
        {
            'name': '🔍 Google Search',
            'url': f"https://www.google.com/search?q={encoded_query}+drama+streaming",
            'description': 'Cari di semua situs'
        }
    ]
    
    # Create keyboard
    keyboard = types.InlineKeyboardMarkup()
    
    for site in drama_sites:
        keyboard.add(types.InlineKeyboardButton(
            site['name'],
            url=site['url']
        ))
    
    bot.reply_to(
        message,
        f"📺 <b>HASIL PENCARIAN DRAMA:</b>\n\n"
        f"Judul: <code>{query}</code>\n\n"
        f"<b>PILIH SITUS STREAMING:</b>\n"
        f"• Semua situs gratis\n"
        f"• Subtitle Indonesia tersedia\n"
        f"• Kualitas HD\n\n"
        f"<i>Klik tombol untuk membuka situs streaming</i>",
        reply_markup=keyboard
    )

# ============ FITUR 6: ANIME ============
@bot.message_handler(commands=['anime'])
def anime_command(message):
    """Anime command handler"""
    if len(message.text.split()) > 1:
        query = message.text.split(' ', 1)[1]
        search_anime(message, query)
    else:
        msg = bot.send_message(
            message.chat.id,
            "🇯🇵 <b>CARI ANIME:</b>\n\n"
            "Kirim judul anime:\n"
            "Contoh: Attack on Titan, Demon Slayer, One Piece"
        )
        bot.register_next_step_handler(msg, search_anime)

def search_anime(message, query=None):
    """Search anime"""
    if not query:
        query = message.text
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    encoded_query = urllib.parse.quote(query)
    
    # Anime streaming sites
    anime_sites = [
        {
            'name': '🎌 GogoAnime',
            'url': f"https://gogoanime3.co/search.html?keyword={encoded_query}",
            'description': 'Anime terlengkap'
        },
        {
            'name': '🌸 AniWave',
            'url': f"https://aniwave.to/filter?keyword={encoded_query}",
            'description': 'Anime terbaru'
        },
        {
            'name': '🗻 AnimeIndo',
            'url': f"https://animeindo.one/?s={encoded_query}",
            'description': 'Subtitle Indonesia'
        },
        {
            'name': '🔍 Google Search',
            'url': f"https://www.google.com/search?q={encoded_query}+anime+streaming",
            'description': 'Cari di semua situs'
        }
    ]
    
    # Create keyboard
    keyboard = types.InlineKeyboardMarkup()
    
    for site in anime_sites:
        keyboard.add(types.InlineKeyboardButton(
            site['name'],
            url=site['url']
        ))
    
    bot.reply_to(
        message,
        f"🇯🇵 <b>HASIL PENCARIAN ANIME:</b>\n\n"
        f"Judul: <code>{query}</code>\n\n"
        f"<b>PILIH SITUS STREAMING:</b>\n"
        f"• Semua situs gratis\n"
        f"• Subtitle Indonesia tersedia\n"
        f"• Kualitas HD\n\n"
        f"<i>Klik tombol untuk membuka situs streaming</i>",
        reply_markup=keyboard
    )

# ============ FITUR 7: LIRIK LAGU ============
@bot.message_handler(commands=['lyrics', 'lirik'])
def lyrics_command(message):
    """Lyrics command handler"""
    if len(message.text.split()) > 1:
        query = message.text.split(' ', 1)[1]
        search_lyrics(message, query)
    else:
        msg = bot.send_message(
            message.chat.id,
            "📜 <b>CARI LIRIK LAGU:</b>\n\n"
            "Kirim judul lagu dan artis:\n"
            "Contoh: Bohemian Rhapsody Queen"
        )
        bot.register_next_step_handler(msg, search_lyrics)

def search_lyrics(message, query=None):
    """Search lyrics"""
    if not query:
        query = message.text
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Search using Genius API
        song = genius.search_song(query)
        
        if song and song.lyrics:
            lyrics = song.lyrics[:3000]  # Limit for Telegram
            
            # Create message
            lyrics_text = f"""
🎵 <b>{song.title} - {song.artist}</b>

📜 <b>LIRIK:</b>

{lyrics}

🔗 <a href="{song.url}">Buka di Genius.com</a>
"""
            
            bot.reply_to(message, lyrics_text, disable_web_page_preview=True)
        else:
            bot.reply_to(
                message,
                f"❌ Lirik tidak ditemukan untuk <code>{query}</code>\n\n"
                f"Coba format: <code>JudulLagu NamaArtis</code>"
            )
    
    except Exception as e:
        print(f"❌ Lyrics search error: {e}")
        bot.reply_to(
            message,
            f"❌ Gagal mencari lirik. Coba lagi nanti.\n\n"
            f"Tips: Cari di Google dengan kata kunci:\n"
            f"<code>{query} lyrics</code>"
        )

# ============ FITUR 8: MEME GENERATOR ============
@bot.message_handler(commands=['meme'])
def meme_command(message):
    """Send random meme"""
    memes = [
        "https://i.imgflip.com/1bij.jpg",  # One Does Not Simply
        "https://i.imgflip.com/1g8my4.jpg",  # 10 Guy
        "https://i.imgflip.com/1otk96.jpg",  # Drake Hotline Bling
        "https://i.imgflip.com/30b1gx.jpg",  # Change My Mind
        "https://i.imgflip.com/1h7in3.jpg",  # Distracted Boyfriend
        "https://i.imgflip.com/1c1uej.jpg",  # Grumpy Cat
        "https://i.imgflip.com/26am.jpg",    # Foul Bachelor Frog
        "https://i.imgflip.com/23ls.jpg",    # Success Kid
    ]
    
    meme_url = random.choice(memes)
    
    bot.send_photo(
        message.chat.id,
        meme_url,
        caption="🖼 <b>Random Meme</b>\n\nGunakan /meme lagi untuk yang lain!"
    )

# ============ FITUR 9: STATS & INFO ============
@bot.message_handler(commands=['stats', 'statistik'])
def stats_command(message):
    """Show bot statistics"""
    try:
        conn = sqlite3.connect('superbot.db')
        c = conn.cursor()
        
        # Count users
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        
        # Count downloads
        c.execute("SELECT COUNT(*) FROM downloads")
        download_count = c.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""
📊 <b>STATISTIK BOT</b>

👥 <b>Total Pengguna:</b> {user_count}
📥 <b>Total Download:</b> {download_count}
🕒 <b>Uptime:</b> 24/7

<b>FITUR TERSEDIA:</b>
✅ Film Streaming (LK21, Dutafilm, dll)
✅ Musik Player (YouTube & YouTube Music)
✅ Video Downloader (YouTube)
✅ Drama China/Korea
✅ Anime Streaming
✅ Jokes Generator
✅ Lirik Lagu
✅ Meme Generator

<b>PERINTAH:</b>
/movie - Cari film
/music - Cari musik
/video - Download video
/drama - Cari drama
/anime - Cari anime
/joke - Dapatkan joke
/lyrics - Cari lirik
/meme - Random meme
/help - Bantuan lengkap

🔥 <i>Semua fitur 100% GRATIS!</i>
"""
        
        bot.reply_to(message, stats_text)
    
    except:
        bot.reply_to(
            message,
            "📊 <b>Bot sedang berjalan dengan baik!</b>\n\n"
            "Gunakan /help untuk melihat semua fitur."
        )

# ============ FITUR 10: HELP COMMAND ============
@bot.message_handler(commands=['start', 'help', 'bantuan'])
def help_command(message):
    """Help command"""
    help_text = """
🤖 <b>TELEGRAM SUPER BOT</b>
<i>Semua Fitur dalam Satu Bot - 100% GRATIS!</i>

<b>🎬 FITUR FILM:</b>
/movie [judul] - Cari & streaming film
/film [judul] - Sama seperti /movie

<b>🎵 FITUR MUSIK:</b>
/music [judul] - Cari & download musik
/play [judul] - Sama seperti /music
/lagu [judul] - Cari lagu Indonesia

<b>📥 FITUR DOWNLOAD:</b>
/video [url] - Download video YouTube
/download [url] - Sama seperti /video

<b>📺 FITUR DRAMA:</b>
/drama [judul] - Drama China/Korea
/cdrama [judul] - Drama China
/kdrama [judul] - Drama Korea

<b>🇯🇵 FITUR ANIME:</b>
/anime [judul] - Cari anime

<b>🎭 FITUR HIBURAN:</b>
/joke - Dapatkan joke lucu
/lyrics [judul] - Cari lirik lagu
/meme - Random meme

<b>📊 LAINNYA:</b>
/stats - Statistik bot
/help - Tampilkan pesan ini

<b>💡 CONTOH PENGGUNAAN:</b>
/movie Avengers Endgame
/music Coldplay Yellow
/video https://youtube.com/watch?v=xxx
/drama Love O2O
/anime Attack on Titan
/joke
/lyrics Bohemian Rhapsody Queen

<b>⚠️ CATATAN:</b>
• Bot hanya menyediakan LINK ke situs eksternal
• Gunakan dengan bijak
• Semua konten gratis

🔥 <b>DIBUAT DENGAN ❤️ UNTUK INDONESIA</b>
"""
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎬 Cari Film", callback_data="quick_movie"),
        types.InlineKeyboardButton("🎵 Cari Musik", callback_data="quick_music"),
        types.InlineKeyboardButton("📺 Cari Drama", callback_data="quick_drama"),
        types.InlineKeyboardButton("🇯🇵 Cari Anime", callback_data="quick_anime")
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=keyboard)

# ============ QUICK ACTIONS ============
@bot.callback_query_handler(func=lambda call: call.data.startswith('quick_'))
def quick_action(call):
    """Handle quick actions"""
    action = call.data.replace('quick_', '')
    
    if action == 'movie':
        msg = bot.send_message(call.message.chat.id, "🎬 Kirim judul film:")
        bot.register_next_step_handler(msg, search_movies)
    elif action == 'music':
        msg = bot.send_message(call.message.chat.id, "🎵 Kirim judul lagu:")
        bot.register_next_step_handler(msg, process_music_search)
    elif action == 'drama':
        msg = bot.send_message(call.message.chat.id, "📺 Kirim judul drama:")
        bot.register_next_step_handler(msg, search_drama)
    elif action == 'anime':
        msg = bot.send_message(call.message.chat.id, "🇯🇵 Kirim judul anime:")
        bot.register_next_step_handler(msg, search_anime)
    
    bot.answer_callback_query(call.id)

# ============ BACK BUTTONS ============
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_jokes')
def back_to_jokes(call):
    """Back to jokes menu"""
    send_joke(call.message)

# ============ START BOT ============
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 TELEGRAM SUPER BOT")
    print("="*50)
    print(f"Bot: @{bot.get_me().username}")
    print("Fitur: Film, Musik, Video, Drama, Anime, Jokes")
    print("Status: 🟢 AKTIF")
    print("="*50 + "\n")
    
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("🔄 Restarting in 5 seconds...")
        time.sleep(5)