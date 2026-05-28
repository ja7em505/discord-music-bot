#!/bin/bash
# Music Bot - VPS Setup Script (Ubuntu/Debian)

echo "🎵 تركيب بوت ديسكورد على السيرفر..."

# تحديث النظام
sudo apt update && sudo apt upgrade -y

# تركيب Python + FFmpeg + Git + Screen
sudo apt install -y python3 python3-pip ffmpeg git screen

# تركيب Deno (JS runtime for yt-dlp)
curl -fsSL https://deno.land/install.sh | sh
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# سحب البوت من GitHub (بعد ما ترفعه)
# git clone https://github.com/your-username/discord-music-bot.git
# cd discord-music-bot

# تركيب مكتبات بايثون
pip3 install -r requirements.txt

# إنشاء ملف .env
echo "📝 حط توكن البوت في .env"

echo ""
echo "✅ خلص! شغّل البوت:"
echo "screen -S musicbot"
echo "cd ~/discord-music-bot"
echo "python3 main.py"
