import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from collections import deque
import os
import json
import random
print(os.getcwd())

import os
LOG_CHANNEL_ID = 1499818861850132490

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=",", intents=intents)
tree = bot.tree

music_queue = deque()
current_song = None

def load_credits():
    try:
        with open("credits.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_credits(data):
    with open("credits.json", "w") as f:
        json.dump(data, f, indent=4)

credits = load_credits()

def load_game_settings():
    try:
        with open("game_settings.json", "r") as f:
            return json.load(f)
    except:
        return {
            "rocket_rigged": False,
            "limbo_rigged": False,
            "mines_rigged": False,
            "plinko_rigged": False,
            "global_win_chance": 20
        }

def save_game_settings(data):
    with open("game_settings.json", "w") as f:
        json.dump(data, f, indent=4)

game_settings = load_game_settings()

class RocketView(discord.ui.View):

    def __init__(self, user, bet):
        super().__init__(timeout=30)

        self.user = user
        self.bet = bet
        self.multiplier = 1.00
        self.crashed = False
        self.cashed_out = False

    @discord.ui.button(label="💸 Cashout", style=discord.ButtonStyle.green)
    async def cashout(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user != self.user:
            await interaction.response.send_message(
                "❌ This is not your game.",
                ephemeral=True
            )
            return

        if self.crashed:
            await interaction.response.send_message(
                "❌ Rocket already crashed.",
                ephemeral=True
            )
            return

        if self.cashed_out:
            return

        self.cashed_out = True

        winnings = int(self.bet * self.multiplier)

        user_id = str(self.user.id)

        credits[user_id] += winnings
        save_credits(credits)

        await interaction.response.send_message(
            f"💰 Cashed out at {self.multiplier:.2f}x\n"
            f"You won {winnings} credits!"
        )

# ================= AUDIO =================

async def get_audio(query):
    ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'skip_download': True,
    'default_search': 'scsearch1',   # 👈 IMPORTANT CHANGE
    'extract_flat': False
}

    def extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(query, download=False)

    data = await asyncio.to_thread(extract)

    if 'entries' in data:
        data = data['entries'][0]

    return data['url'], data['title'], data.get('thumbnail')

# ================= PLAYER =================

async def play_next(ctx_or_interaction):
    global current_song

    vc = ctx_or_interaction.guild.voice_client
    if not vc:
        return

    if not music_queue:
        current_song = None
        return

    url, title, thumbnail, requester = music_queue.popleft()
    current_song = title

    source = discord.FFmpegPCMAudio(
        url,
        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        options="-vn"
    )

    def after(e):
        async def next_song():
            await asyncio.sleep(1)
            await play_next(ctx_or_interaction)

        asyncio.run_coroutine_threadsafe(next_song(), bot.loop)

    vc.play(source, after=after)

    # ===== PANEL =====
    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{title}**",
        color=discord.Color.blurple()
    )

    embed.add_field(name="👤 Requested by", value=requester.mention, inline=True)

    if music_queue:
        embed.add_field(name="⏭ Next", value=music_queue[0][1], inline=False)

    if len(music_queue) > 1:
        upcoming = "\n".join([song[1] for song in list(music_queue)[:3]])
        embed.add_field(name="📃 Up Next", value=upcoming, inline=False)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text="Music Player")

    view = MusicControls(vc)

    if isinstance(ctx_or_interaction, discord.Interaction):
        await ctx_or_interaction.followup.send(embed=embed, view=view)
    else:
        await ctx_or_interaction.send(embed=embed, view=view)

# ================= BUTTON UI =================

class MusicControls(discord.ui.View):
    def __init__(self, vc):
        super().__init__(timeout=None)
        self.vc = vc

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.primary)
    async def pause(self, interaction, button):
        if self.vc.is_playing():
            self.vc.pause()
        await interaction.response.defer()

    @discord.ui.button(label="▶ Resume", style=discord.ButtonStyle.success)
    async def resume(self, interaction, button):
        if self.vc.is_paused():
            self.vc.resume()
        await interaction.response.defer()

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction, button):
        self.vc.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction, button):
        await self.vc.disconnect()
        await interaction.response.defer()

# ================= MUSIC COMMANDS =================

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        return await ctx.send("Join VC first")

    vc = ctx.guild.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()

    url, title, thumbnail = await get_audio(query)

    music_queue.append((url, title, thumbnail, ctx.author))

    if not vc.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Added to queue: {title}")

@tree.command(name="play")
async def slash_play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice:
        return await interaction.followup.send("Join VC first")

    vc = interaction.guild.voice_client
    if not vc:
        vc = await interaction.user.voice.channel.connect()

    url, title, thumbnail = await get_audio(query)

    music_queue.append((url, title, thumbnail, interaction.user))

    if not vc.is_playing():
        await play_next(interaction)
    else:
        await interaction.followup.send(f"➕ Added: {title}")

@bot.command()
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()

@tree.command(name="skip")
async def slash_skip(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped")


# ================= MODERATION =================

def load_replies():
    try:
        with open("autoreplies.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_replies(data):
    with open("autoreplies.json", "w") as f:
        json.dump(data, f, indent=4)

autoreplies = load_replies()


# Simple in-memory storage
tags = {}

tags = {}

import json
import os

# load or create file
if os.path.exists("tags.json"):
    with open("tags.json", "r") as f:
        tags = json.load(f)
else:
    tags = {}

def save_tags():
    with open("tags.json", "w") as f:
        json.dump(tags, f, indent=4)

# -------------------------
# PREFIX
@bot.command()
@commands.has_permissions(administrator=True)
async def settag(ctx, member: discord.Member, *, tag_text: str):
    tags[str(member.id)] = tag_text
    save_tags()
    await ctx.send(f"Tag set for {member.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def tag(ctx, member: discord.Member):
    tag = tags.get(str(member.id))

    if tag:
        await ctx.send(f"{member.mention} = {tag}")
    else:
        await ctx.send(f"{member.mention} has no tag.")


# SLASH
@bot.tree.command(name="settag")
@app_commands.checks.has_permissions(administrator=True)
async def slash_settag(interaction: discord.Interaction, member: discord.Member, tag_text: str):
    tags[str(member.id)] = tag_text
    save_tags()
    await interaction.response.send_message(f"Tag set for {member.mention}")

@bot.tree.command(name="tag")
@app_commands.checks.has_permissions(administrator=True)
async def slash_tag(interaction: discord.Interaction, member: discord.Member):
    tag = tags.get(str(member.id))

    if tag:
        await interaction.response.send_message(f"{member.mention} = {tag}")
    else:
        await interaction.response.send_message(f"{member.mention} has no tag.")

# -------------------------
# PREFIX COMMAND
# -------------------------

@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You must be in a voice channel.")

# -------------------------
# SLASH COMMAND
# -------------------------

@bot.tree.command(name="join")
async def slash_join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"Joined {channel.name}")
    else:
        await interaction.response.send_message("You must be in a voice channel.")
        
#-------------Ping--------------

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)  # convert to ms
    await interaction.response.send_message(f"🏓 Pong! {latency}ms")

#------------,ban-------------

@bot.command()
@commands.has_permissions(moderate_members=True)
async def removetimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"Removed timeout from {member.mention}")

#------------/ban-------------

@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.mention}")

#----------------/timeout-------------

from datetime import timedelta

@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    duration = timedelta(minutes=minutes)
    await member.timeout(duration)
    await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes")

#----------------------/role--------------

@bot.tree.command(name="role", description="Give or remove a role")
@app_commands.checks.has_permissions(manage_roles=True)
async def role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role)
        await interaction.response.send_message(f"Removed {role.name} from {member.mention}")
    else:
        await member.add_roles(role)
        await interaction.response.send_message(f"Added {role.name} to {member.mention}")

@app_commands.checks.has_permissions(administrator=True)
@bot.tree.command(name="autoreply", description="Add custom auto reply")
async def autoreply(interaction: discord.Interaction, trigger: str, response: str):
    autoreplies[trigger.lower()] = response
    save_replies(autoreplies)
    await interaction.response.send_message(f"Added reply: '{trigger}' → '{response}'")

#----------auto response----------

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()

    for trigger, reply in autoreplies.items():
        if trigger in content:
            await message.channel.send(reply)
            break

    await bot.process_commands(message)

@bot.tree.command(name="listautoreplies", description="Show all auto replies")
@app_commands.checks.has_permissions(administrator=True)
async def listautoreplies(interaction: discord.Interaction):

    if not autoreplies:
        await interaction.response.send_message("No auto replies setup.")
        return

    msg = "**Auto Replies:**\n"

    for trigger, reply in autoreplies.items():
        msg += f"• `{trigger}` → `{reply}`\n"

    await interaction.response.send_message(msg)

@bot.tree.command(name="removeautoreply", description="Remove an auto reply")
@app_commands.checks.has_permissions(administrator=True)
async def removeautoreply(interaction: discord.Interaction, trigger: str):

    trigger = trigger.lower()

    if trigger not in autoreplies:
        await interaction.response.send_message("❌ Trigger not found.")
        return

    del autoreplies[trigger]
    save_replies(autoreplies)

    await interaction.response.send_message(
        f"✅ Removed auto reply for `{trigger}`"
    )



@bot.tree.command(name="setwinchance")
@app_commands.checks.has_permissions(administrator=True)
async def setwinchance(
    interaction: discord.Interaction,
    percent: int
):

    if percent < 1 or percent > 100:
        await interaction.response.send_message(
            "❌ Use 1-100",
            ephemeral=True
        )
        return

    game_settings["global_win_chance"] = percent
    save_game_settings(game_settings)

    await interaction.response.send_message(
        f"✅ Win chance set to {percent}%",
        ephemeral=True
    )

@bot.tree.command(name="balance")
async def balance(interaction: discord.Interaction):

    user_id = str(interaction.user.id)

    if user_id not in credits:
        credits[user_id] = 0
        save_credits(credits)

    await interaction.response.send_message(
        f"💰 Balance: {credits[user_id]}"
    )

@bot.tree.command(name="rigrocket")
@app_commands.checks.has_permissions(administrator=True)
async def rigrocket(interaction: discord.Interaction):

    game_settings["rocket_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🚀 Rocket troll mode enabled.",
        ephemeral=True
    )

@bot.tree.command(name="unrigrocket")
@app_commands.checks.has_permissions(administrator=True)
async def unrigrocket(interaction: discord.Interaction):

    game_settings["rocket_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Rocket normal mode enabled.",
        ephemeral=True
    )

@bot.tree.command(name="rocket", description="Play Rocket")
async def rocket(interaction: discord.Interaction, bet: int):

    user_id = str(interaction.user.id)

    if user_id not in credits:
        credits[user_id] = 0

    if bet <= 0:
        await interaction.response.send_message(
            "❌ Invalid bet."
        )
        return

    if credits[user_id] < bet:
        await interaction.response.send_message(
            "❌ Not enough credits."
        )
        return

    credits[user_id] -= bet
    save_credits(credits)

    view = RocketView(interaction.user, bet)

    embed = discord.Embed(
        title="🚀 Rocket Game",
        description="Multiplier: **1.00x**",
        color=discord.Color.blue()
    )

    message = await interaction.response.send_message(
        embed=embed,
        view=view
    )

    msg = await interaction.original_response()

    roll = random.randint(1, 100)

# TROLL MODE
if game_settings["rocket_rigged"]:

    crash_point = round(random.uniform(1.00, 1.30), 2)

# NORMAL MODE
else:

    # lose chance
    if roll > game_settings["global_win_chance"]:

        crash_point = round(random.uniform(1.00, 2.50), 2)

    # win chance
    else:

        crash_point = round(random.uniform(3.00, 15.00), 2)

    while not view.crashed and not view.cashed_out:
        
        await asyncio.sleep(1)

    view.multiplier += 0.25

    # AUTO CASHOUT
    if auto_cashout is not None:

        if view.multiplier >= auto_cashout:

            if not view.cashed_out:

                view.cashed_out = True

                winnings = int(bet * view.multiplier)

                credits[user_id] += winnings
                save_credits(credits)

                auto_embed = discord.Embed(
                    title="💰 Auto Cashed Out!",
                    description=(
                        f"Auto cashed out at "
                        f"**{view.multiplier:.2f}x**\n"
                        f"You won {winnings} credits!"
                    ),
                    color=discord.Color.gold()
                )

                auto_embed.set_image(
                    url="https://media.giphy.com/media/l3vR85PnGsBwu1PFK/giphy.gif"
                )

                await msg.edit(embed=auto_embed, view=None)
                return

    # CRASH CHECK
    if view.multiplier >= crash_point:

        view.crashed = True

        crash_embed = discord.Embed(
            title="💥 Rocket Crashed!",
            description=(
                f"Crashed at "
                f"**{view.multiplier:.2f}x**\n"
                f"You lost {bet} credits."
            ),
            color=discord.Color.red()
        )

        crash_embed.set_image(
            url="https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif"
        )

        await msg.edit(embed=crash_embed, view=None)
        return

    # LIVE EMBED
    live_embed = discord.Embed(
        title="🚀 Rocket Flying",
        description=(
            f"Multiplier: "
            f"**{view.multiplier:.2f}x**"
        ),
        color=discord.Color.green()
    )

    live_embed.set_image(
        url="https://media.giphy.com/media/l3vR85PnGsBwu1PFK/giphy.gif"
    )

    await msg.edit(embed=live_embed, view=view)
                return

    # CRASH CHECK
    if view.multiplier >= crash_point:

        view.crashed = True

        crash_embed = discord.Embed(
            title="💥 Rocket Crashed!",
            description=(
                f"Crashed at **{view.multiplier:.2f}x**\n"
                f"You lost {bet} credits."
            ),
            color=discord.Color.red()
        )

        crash_embed.set_image(
            url="https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif"
        )

        await msg.edit(embed=crash_embed, view=None)
       
        return

    # LIVE MULTIPLIER EMBED
    live_embed = discord.Embed(
        title="🚀 Rocket Flying",
        description=(
            f"Multiplier: **{view.multiplier:.2f}x**"
        ),
        color=discord.Color.green()
    )

    live_embed.set_image(
        url="https://media.giphy.com/media/l3vR85PnGsBwu1PFK/giphy.gif"
    )

    await msg.edit(embed=live_embed, view=view)

@bot.tree.command(name="addcredits", description="Add credits to a user")
@app_commands.checks.has_permissions(administrator=True)
async def addcredits(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    user_id = str(member.id)

    if user_id not in credits:
        credits[user_id] = 0

    credits[user_id] += amount

    save_credits(credits)

    await interaction.response.send_message(
        f"✅ Added {amount} credits to {member.mention}",
        ephemeral=True
    )




# ================= READY =================

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(os.getenv("TOKEN"))
