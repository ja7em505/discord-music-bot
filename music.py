import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import re

DENO_PATH = r"C:\Users\JA7EM\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe"
os.environ["PATH"] = DENO_PATH + os.pathsep + os.environ.get("PATH", "")

BANNER_URL = "https://media.discordapp.net/attachments/1354939440979771484/1509431762017587291/ChatGPT_Image_21_2026_04_29_12_.png?ex=6a19275f&is=6a17d5df&hm=387178017ead99b2492a78b3c248c8b83f5aa365a9fcd55c44edd2f0116fce1f&=&format=webp&quality=lossless&width=847&height=847"
COLOR_PRO = 0x00FF88
COLOR_ERROR = 0xFF4444
COLOR_WARN = 0xFFAA00

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

YDL_OPTIONS = {
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "extract_flat": "in_playlist",
    "noplaylist": True,
    "default_search": "ytsearch5",
    "source_address": "0.0.0.0",
    "retries": 10,
    "fragment_retries": 10,
    "sleep_interval": 3,
    "max_sleep_interval": 6,
    "ignoreerrors": True,
    "extractor_args": {"youtube": {"skip": ["webpage"], "player_client": ["android", "tv"]}},
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-us,en;q=0.5",
    },
}


class Song:
    def __init__(self, data: dict, requester: discord.Member):
        self.title = data.get("title", "Unknown")
        self.url = data.get("webpage_url") or data.get("url") or f"https://youtube.com/watch?v={data.get('id', '')}"
        self.duration = data.get("duration", 0)
        self.thumbnail = data.get("thumbnail", "")
        self.requester = requester
        self.channel = data.get("channel", data.get("uploader", "Unknown"))
        self.channel_url = data.get("channel_url", data.get("uploader_url", ""))
        self.views = data.get("view_count", 0)
        self.likes = data.get("like_count", 0)

    def __str__(self):
        return f"**{self.title}**"


class PlayerState:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current = None
        self.voice = None
        self.loop = False
        self.volume = 0.5

    def clear(self):
        self.queue = asyncio.Queue()
        self.current = None
        self.loop = False

    @property
    def queue_list(self):
        items = []
        while not self.queue.empty():
            try:
                items.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        for item in items:
            self.queue.put_nowait(item)
        return items


class PlayerView(discord.ui.View):
    def __init__(self, cog: "Music", guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    def get_state(self):
        return self.cog.get_state(self.guild_id)

    @discord.ui.button(label="", emoji="⏯", style=discord.ButtonStyle.blurple)
    async def play_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.get_state()
        if state.voice and state.voice.is_playing():
            state.voice.pause()
            await interaction.response.send_message("⏸️ تم الإيقاف المؤقت", ephemeral=True)
        elif state.voice and state.voice.is_paused():
            state.voice.resume()
            await interaction.response.send_message("▶️ تم الاستئناف", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شي يشتغل", ephemeral=True)

    @discord.ui.button(label="", emoji="⏭", style=discord.ButtonStyle.blurple)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.get_state()
        if state.voice and state.voice.is_playing():
            state.voice.stop()
            await interaction.response.send_message("⏭️ تم تخطي الأغنية", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما فيه شي يتخطى", ephemeral=True)

    @discord.ui.button(label="", emoji="⏹", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.get_state()
        state.clear()
        if state.voice and state.voice.is_connected():
            state.voice.stop()
            await state.voice.disconnect()
            state.voice = None
        await interaction.response.send_message("👋 طلعت من الروم", ephemeral=True)

    @discord.ui.button(label="", emoji="🔊", style=discord.ButtonStyle.green)
    async def vol_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.get_state()
        state.volume = min(1.0, state.volume + 0.1)
        if state.voice and state.voice.source and hasattr(state.voice.source, "volume"):
            state.voice.source.volume = state.volume
        await interaction.response.send_message(f"🔊 الصوت: {int(state.volume * 100)}%", ephemeral=True)

    @discord.ui.button(label="", emoji="🔉", style=discord.ButtonStyle.green)
    async def vol_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.get_state()
        state.volume = max(0.0, state.volume - 0.1)
        if state.voice and state.voice.source and hasattr(state.voice.source, "volume"):
            state.voice.source.volume = state.volume
        await interaction.response.send_message(f"🔉 الصوت: {int(state.volume * 100)}%", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild_id: int) -> PlayerState:
        if guild_id not in self.states:
            self.states[guild_id] = PlayerState()
        return self.states[guild_id]

    async def search_youtube(self, query: str) -> list:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            if re.match(r"^https?://", query):
                data = ydl.extract_info(query, download=False)
                if "entries" in data:
                    return data["entries"]
                return [data]
            else:
                data = ydl.extract_info(f"ytsearch5:{query}", download=False)
                return data.get("entries", [])

    async def get_audio_url(self, url: str):
        with youtube_dl.YoutubeDL({"format": "bestaudio/best", "quiet": True}) as ydl:
            data = ydl.extract_info(url, download=False)
            return data["url"]

    async def play_next(self, guild_id: int):
        state = self.get_state(guild_id)
        if state.voice is None or not state.voice.is_connected():
            return

        if state.loop and state.current:
            state.queue.put_nowait(state.current)

        try:
            if state.queue.empty():
                state.current = None
                await self.now_playing_embed(state.voice, None, end=True)
                return

            state.current = await state.queue.get()
            audio_url = await self.get_audio_url(state.current.url)
            raw_source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(raw_source, volume=state.volume)

            def after(error):
                if error:
                    print(f"Playback error: {error}")
                coro = self.play_next(guild_id)
                fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"After callback error: {e}")

            state.voice.play(source, after=after)
            await self.now_playing_embed(state.voice, state.current)

        except Exception as e:
            print(f"play_next error: {e}")
            await self.play_next(guild_id)

    async def connect_voice(self, ctx: commands.Context) -> bool:
        state = self.get_state(ctx.guild.id)
        if state.voice and state.voice.is_connected():
            return True

        if not ctx.author.voice:
            await ctx.send(embed=self.error_embed("يجب أن تكون في روم صوتي أولاً!"))
            return False

        channel = ctx.author.voice.channel
        try:
            state.voice = await channel.connect(timeout=20, reconnect=True)
            return True
        except Exception as e:
            await ctx.send(embed=self.error_embed(f"تعذر الاتصال بالروم الصوتي: {e}"))
            return False

    def embed(self, description="", title="") -> discord.Embed:
        e = discord.Embed(description=description, color=COLOR_PRO)
        e.set_footer(text="🎵 Music Bot", icon_url=BANNER_URL)
        e.set_image(url=BANNER_URL)
        if title:
            e.title = title
        return e

    def error_embed(self, text: str) -> discord.Embed:
        e = discord.Embed(description=f"❌ {text}", color=COLOR_ERROR)
        e.set_footer(text="🎵 Music Bot")
        return e

    def success_embed(self, text: str) -> discord.Embed:
        e = discord.Embed(description=f"✅ {text}", color=COLOR_PRO)
        e.set_footer(text="🎵 Music Bot")
        return e

    def format_duration(self, seconds: int) -> str:
        if not seconds or seconds <= 0:
            return "Live"
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

    async def now_playing_embed(self, voice: discord.VoiceClient, song: Song | None, end=False):
        if not voice or not voice.channel:
            return
        channel = voice.channel
        text_channel = next(
            (c for c in channel.guild.text_channels if c.permissions_for(channel.guild.me).send_messages),
            None,
        )
        if not text_channel:
            return

        if end or not song:
            embed = discord.Embed(
                title="⏹️ انتهت قائمة التشغيل",
                description="أضف أغنية جديدة بـ `!play`",
                color=COLOR_WARN,
            )
            embed.set_footer(text="🎵 Music Bot")
            embed.set_image(url=BANNER_URL)
            await text_channel.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎶 الآن يتم التشغيل",
            description=f"[**{song.title}**]({song.url})",
            color=COLOR_PRO,
        )
        embed.add_field(name="⏱ المدة", value=self.format_duration(song.duration), inline=True)
        embed.add_field(name="👤 طلب بواسطة", value=song.requester.mention, inline=True)
        embed.add_field(name="📢 القناة", value=f"[{song.channel}]({song.channel_url})" if song.channel_url else song.channel, inline=True)
        if song.views:
            embed.add_field(name="👁 المشاهدات", value=f"{song.views:,}", inline=True)
        if song.likes:
            embed.add_field(name="👍 الإعجابات", value=f"{song.likes:,}", inline=True)
        if song.thumbnail:
            embed.set_thumbnail(url=song.thumbnail)
        embed.set_image(url=BANNER_URL)
        embed.set_footer(text="🎵 Music Bot")

        view = PlayerView(self, text_channel.guild.id)
        await text_channel.send(embed=embed, view=view)

    # ──────────────────────────────── Commands ────────────────────────────────

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        await ctx.message.add_reaction("🔍")
        if not await self.connect_voice(ctx):
            return

        state = self.get_state(ctx.guild.id)
        results = await self.search_youtube(query)
        if not results:
            await ctx.send(embed=self.error_embed("ما لقيت شيء بهذا الاسم!"))
            return

        if len(results) > 1 and not re.match(r"^https?://", query):
            choices = []
            for i, entry in enumerate(results[:5]):
                dur = entry.get("duration", 0)
                dur_str = self.format_duration(dur)
                title = entry.get("title", "Unknown")
                choices.append(f"**{i+1}.** {title} [{dur_str}]")

            embed = discord.Embed(
                title="🔎 اختر رقم الأغنية",
                description="\n".join(choices),
                color=COLOR_PRO,
            )
            embed.set_image(url=BANNER_URL)
            embed.set_footer(text="اكتب رقم 1-5 خلال 20 ثانية")
            msg = await ctx.send(embed=embed)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit() and 1 <= int(m.content) <= 5

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=20)
                choice = int(reply.content) - 1
                selected = results[choice]
                await reply.delete()
            except asyncio.TimeoutError:
                await msg.edit(embed=self.error_embed("انتهى الوقت! استخدم `!play <اسم>` مرة ثانية"))
                return
            await msg.delete()
        else:
            selected = results[0]

        song = Song(selected, ctx.author)

        if state.current and state.voice.is_playing():
            await state.queue.put(song)
            pos = len(state.queue_list)
            await ctx.send(
                embed=discord.Embed(
                    title="📥 أضيفت إلى قائمة التشغيل",
                    description=f"[**{song.title}**]({song.url})",
                    color=COLOR_PRO,
                )
                .add_field(name="الموقع", value=f"#{pos}", inline=True)
                .add_field(name="المدة", value=self.format_duration(song.duration), inline=True)
                .add_field(name="طلب بواسطة", value=ctx.author.mention, inline=True)
                .set_thumbnail(url=song.thumbnail or "")
                .set_image(url=BANNER_URL)
                .set_footer(text="🎵 Music Bot")
            )
        else:
            await state.queue.put(song)
            await ctx.message.add_reaction("✅")
            await self.play_next(ctx.guild.id)

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.voice or not state.voice.is_playing():
            await ctx.send(embed=self.error_embed("ما فيه شي يشتغل عشان تتخطاه!"))
            return
        state.voice.stop()
        await ctx.send(embed=self.success_embed("⏭️ تم تخطي الأغنية"))

    @commands.command(name="stop", aliases=["leave", "fuckoff"])
    async def stop(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.clear()
        if state.voice and state.voice.is_connected():
            state.voice.stop()
            await state.voice.disconnect()
            state.voice = None
        await ctx.send(embed=discord.Embed(description="👋 طلعت من الروم والصف", color=COLOR_PRO).set_image(url=BANNER_URL).set_footer(text="🎵 Music Bot"))

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice and state.voice.is_playing():
            state.voice.pause()
            await ctx.send(embed=self.success_embed("⏸️ تم الإيقاف المؤقت"))
        else:
            await ctx.send(embed=self.error_embed("ما فيه شي يشتغل عشان أوقفه!"))

    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice and state.voice.is_paused():
            state.voice.resume()
            await ctx.send(embed=self.success_embed("▶️ تم الاستئناف"))
        else:
            await ctx.send(embed=self.error_embed("ما فيه شي موقوف عشان أرجع شغله!"))

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        items = state.queue_list

        if not state.current and not items:
            await ctx.send(embed=discord.Embed(description="📭 قائمة التشغيل فاضية", color=COLOR_WARN).set_image(url=BANNER_URL).set_footer(text="🎵 Music Bot"))
            return

        embed = discord.Embed(title="📋 قائمة التشغيل", color=COLOR_PRO)
        embed.set_image(url=BANNER_URL)
        embed.set_footer(text="🎵 Music Bot")

        if state.current:
            status = "▶️" if state.voice and state.voice.is_playing() else "⏸️" if state.voice and state.voice.is_paused() else "⏹️"
            embed.add_field(
                name=f"{status} الحالي",
                value=f"[**{state.current.title}**]({state.current.url})\nطلب: {state.current.requester.mention}",
                inline=False,
            )

        if items:
            queue_text = ""
            for i, song in enumerate(items[:10]):
                queue_text += f"`{i+1}.` [**{song.title[:50]}**]({song.url}) - {song.requester.mention}\n"
            if len(items) > 10:
                queue_text += f"\n...و {len(items) - 10} أغاني إضافية"
            embed.add_field(name=f"📌 قائمة الانتظار ({len(items)})", value=queue_text, inline=False)
        else:
            embed.add_field(name="📌 قائمة الانتظار", value="فاضية", inline=False)

        embed.add_field(name="🔁 التكرار", value="مفعل ✅" if state.loop else "غير مفعل ❌", inline=True)
        embed.add_field(name="🔊 الصوت", value=f"{int(state.volume * 100)}%", inline=True)

        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.current:
            await ctx.send(embed=self.error_embed("ما فيه أغنية تشتغل حالياً!"))
            return
        embed = discord.Embed(
            title="🎶 الآن يتم التشغيل",
            description=f"[**{state.current.title}**]({state.current.url})",
            color=COLOR_PRO,
        )
        embed.add_field(name="⏱ المدة", value=self.format_duration(state.current.duration), inline=True)
        embed.add_field(name="👤 طلب بواسطة", value=state.current.requester.mention, inline=True)
        embed.add_field(name="📢 القناة", value=state.current.channel, inline=True)
        if state.current.thumbnail:
            embed.set_thumbnail(url=state.current.thumbnail)
        embed.set_image(url=BANNER_URL)
        embed.set_footer(text="🎵 Music Bot")
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, vol: int):
        if vol < 0 or vol > 100:
            await ctx.send(embed=self.error_embed("الصوت يكون بين 0 و 100!"))
            return
        state = self.get_state(ctx.guild.id)
        state.volume = vol / 100
        if state.voice and state.voice.source and hasattr(state.voice.source, "volume"):
            state.voice.source.volume = state.volume
        await ctx.send(embed=self.success_embed(f"🔊 تم تغيير الصوت إلى **{vol}%**"))

    @commands.command(name="loop", aliases=["l"])
    async def loop(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.loop = not state.loop
        status = "مفعل ✅" if state.loop else "غير مفعل ❌"
        await ctx.send(embed=self.success_embed(f"🔁 التكرار {status}"))

    @commands.command(name="help", aliases=["h", "commands"])
    async def help_cmd(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎵 Music Bot - الأوامر",
            description="بوت تشغيل أغاني يوتيوب بروح خرافية",
            color=COLOR_PRO,
        )
        embed.set_image(url=BANNER_URL)
        embed.set_footer(text="🎵 Music Bot")

        commands_list = [
            ("`!play <اسم/رابط>`", "تشغيل أغنية من يوتيوب"),
            ("`!skip`", "تخطي الأغنية الحالية"),
            ("`!stop`", "إيقاف وإخراج البوت من الروم"),
            ("`!pause`", "إيقاف مؤقت"),
            ("`!resume`", "استئناف التشغيل"),
            ("`!queue`", "عرض قائمة التشغيل"),
            ("`!nowplaying`", "عرض الأغنية الحالية"),
            ("`!volume <0-100>`", "التحكم بمستوى الصوت"),
            ("`!loop`", "تشغيل/إيقاف التكرار"),
            ("`!controller`", "عرض لوحة التحكم بالأزرار"),
            ("`!help`", "عرض هذه الرسالة"),
        ]

        for name, desc in commands_list:
            embed.add_field(name=name, value=desc, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="controller", aliases=["面板"])
    async def controller(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🎮 لوحة التحكم",
            description="استخدم الأزرار للتحكم بالأغنية",
            color=COLOR_PRO,
        )
        embed.set_image(url=BANNER_URL)
        embed.set_footer(text="🎵 Music Bot")
        view = PlayerView(self, ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        state = self.get_state(guild.id)
        if state.voice and state.voice.channel:
            members = [m for m in state.voice.channel.members if not m.bot]
            if len(members) == 0:
                state.clear()
                await state.voice.disconnect()
                state.voice = None


async def setup(bot):
    await bot.add_cog(Music(bot))
