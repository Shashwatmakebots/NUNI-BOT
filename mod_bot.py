import asyncio
import io
import json
import os
import random
from datetime import datetime, timedelta, timezone

import aiosqlite
import discord
import wavelink
from discord import app_commands
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont


print(os.getcwd())

LOG_CHANNEL_ID = 1499818861850132490

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=",", intents=intents)


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default.copy() if isinstance(default, dict) else default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_credits():
    return load_json("credits.json", {})


def save_credits(data):
    save_json("credits.json", data)


credits = load_credits()


def load_game_settings():
    return load_json(
        "game_settings.json",
        {
            "rocket_rigged": False,
            "limbo_rigged": False,
            "mines_rigged": False,
            "plinko_rigged": False,
            "global_win_chance": 20,
        },
    )


def save_game_settings(data):
    save_json("game_settings.json", data)


game_settings = load_game_settings()


def load_replies():
    return load_json("autoreplies.json", {})


def save_replies(data):
    save_json("autoreplies.json", data)


autoreplies = load_replies()


tags = load_json("tags.json", {})


def save_tags():
    save_json("tags.json", tags)


class RocketView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=30)
        self.user = user
        self.bet = bet
        self.multiplier = 1.00
        self.crashed = False
        self.cashed_out = False

    @discord.ui.button(label="💸 Cashout", style=discord.ButtonStyle.green)
    async def cashout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("❌ This is not your game.", ephemeral=True)
            return

        if self.crashed:
            await interaction.response.send_message("❌ Rocket already crashed.", ephemeral=True)
            return

        if self.cashed_out:
            await interaction.response.send_message("❌ You already cashed out.", ephemeral=True)
            return

        self.cashed_out = True
        winnings = int(self.bet * self.multiplier)
        user_id = str(self.user.id)
        credits[user_id] = credits.get(user_id, 0) + winnings
        save_credits(credits)

        await interaction.response.send_message(
            f"💰 Cashed out at {self.multiplier:.2f}x\nYou won {winnings} credits!"
        )


# ================= MUSIC =================

async def get_player_for_voice_channel(ctx_or_interaction):
    if isinstance(ctx_or_interaction, discord.Interaction):
        user = ctx_or_interaction.user
        guild = ctx_or_interaction.guild
    else:
        user = ctx_or_interaction.author
        guild = ctx_or_interaction.guild

    if not user.voice or not user.voice.channel:
        return None

    if guild.voice_client:
        return guild.voice_client

    return await user.voice.channel.connect(cls=wavelink.Player)


async def search_tracks(query):
    try:
        return await wavelink.Playable.search(query)
    except wavelink.InvalidNodeException:
        return None


@bot.command(name="play")
async def play(ctx, *, search: str):
    vc = await get_player_for_voice_channel(ctx)

    if not vc:
        await ctx.send("❌ Join a VC first.")
        return

    tracks = await search_tracks(search)

    if tracks is None:
        await ctx.send(
            "❌ Music server is not connected."
        )
        return

    if not tracks:
        await ctx.send("❌ No songs found.")
        return

    track = tracks[0]

    if vc.playing:
        await vc.queue.put_wait(track)
        await ctx.send(
            f"➕ Added to queue: **{track.title}**"
        )
    else:
        await vc.play(track)

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{track.title}**",
        color=discord.Color.blurple(),
    )

    embed.add_field(name="Author", value=track.author)

    await ctx.send(embed=embed)


@bot.tree.command(name="play")
async def slash_play(interaction: discord.Interaction, search: str):
    await interaction.response.defer()

    vc = await get_player_for_voice_channel(interaction)

    if not vc:
        await interaction.followup.send("❌ Join a VC first.")
        return

    tracks = await search_tracks(search)

    if tracks is None:
        await interaction.followup.send(
            "❌ Music server is not connected."
        )
        return

    if not tracks:
        await interaction.followup.send("❌ No songs found.")
        return

    track = tracks[0]

    if vc.playing:
        await vc.queue.put_wait(track)
        await interaction.followup.send(
            f"➕ Added to queue: **{track.title}**"
        )
    else:
        await vc.play(track)

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"**{track.title}**",
        color=discord.Color.blurple(),
    )

    embed.add_field(name="Author", value=track.author)

    await interaction.followup.send(embed=embed)


@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("❌ Nothing is playing.")
        return
    await vc.skip()
    await ctx.send("⏭ Skipped")


@bot.tree.command(name="skip")
async def slash_skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        return
    await vc.skip()
    await interaction.response.send_message("⏭ Skipped")


@bot.command()
async def pause(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("❌ Nothing is playing.")
        return
    await vc.pause()
    await ctx.send("⏸ Paused")


@bot.tree.command(name="pause")
async def slash_pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message("❌ Nothing is playing.", ephemeral=True)
        return
    await vc.pause()
    await interaction.response.send_message("⏸ Paused")


@bot.command()
async def resume(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("❌ Nothing is paused.")
        return
    await vc.resume()
    await ctx.send("▶ Resumed")


@bot.tree.command(name="resume")
async def slash_resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message("❌ Nothing is paused.", ephemeral=True)
        return
    await vc.resume()
    await interaction.response.send_message("▶ Resumed")


@bot.command()
async def stop(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("❌ I am not connected.")
        return
    await vc.disconnect()
    await ctx.send("⏹ Disconnected")


@bot.tree.command(name="stop")
async def slash_stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if not vc:
        await interaction.response.send_message("❌ I am not connected.", ephemeral=True)
        return
    await vc.disconnect()
    await interaction.response.send_message("⏹ Disconnected")


@bot.command(name="queue")
async def queue_command(ctx):
    vc = ctx.voice_client

    if not vc:
        await ctx.send("❌ Nothing is playing.")
        return

    if vc.queue.is_empty:
        await ctx.send("📃 Queue is empty.")
        return

    msg = "\n".join(
        [f"{i+1}. {track.title}" for i, track in enumerate(vc.queue)]
    )

    await ctx.send(f"📃 Queue:\n{msg}")


@bot.tree.command(name="queue")
async def slash_queue(interaction: discord.Interaction):
    vc = interaction.guild.voice_client

    if not vc:
        await interaction.response.send_message("❌ Nothing is playing.")
        return

    if vc.queue.is_empty:
        await interaction.response.send_message("📃 Queue is empty.")
        return

    msg = "\n".join(
        [f"{i+1}. {track.title}" for i, track in enumerate(vc.queue)]
    )

    await interaction.response.send_message(f"📃 Queue:\n{msg}")




# ================= TAGS AND MODERATION =================

@bot.command()
@commands.has_permissions(administrator=True)
async def settag(ctx, member: discord.Member, *, tag_text: str):
    tags[str(member.id)] = tag_text
    save_tags()
    await ctx.send(f"Tag set for {member.mention}")


@bot.command()
@commands.has_permissions(administrator=True)
async def tag(ctx, member: discord.Member):
    tag_text = tags.get(str(member.id))
    if tag_text:
        await ctx.send(f"{member.mention} = {tag_text}")
    else:
        await ctx.send(f"{member.mention} has no tag.")


@bot.tree.command(name="settag")
@app_commands.checks.has_permissions(administrator=True)
async def slash_settag(interaction: discord.Interaction, member: discord.Member, tag_text: str):
    tags[str(member.id)] = tag_text
    save_tags()
    await interaction.response.send_message(f"Tag set for {member.mention}")


@bot.tree.command(name="tag")
@app_commands.checks.has_permissions(administrator=True)
async def slash_tag(interaction: discord.Interaction, member: discord.Member):
    tag_text = tags.get(str(member.id))
    if tag_text:
        await interaction.response.send_message(f"{member.mention} = {tag_text}")
    else:
        await interaction.response.send_message(f"{member.mention} has no tag.")


@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! {latency}ms")


@bot.command()
@commands.has_permissions(moderate_members=True)
async def removetimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"Removed timeout from {member.mention}")


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member.mention}")


@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int):
    duration = timedelta(minutes=minutes)
    await member.timeout(duration)
    await interaction.response.send_message(f"Timed out {member.mention} for {minutes} minutes")


@bot.tree.command(name="role", description="Give or remove a role")
@app_commands.checks.has_permissions(manage_roles=True)
async def role(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role)
        await interaction.response.send_message(f"Removed {role.name} from {member.mention}")
    else:
        await member.add_roles(role)
        await interaction.response.send_message(f"Added {role.name} to {member.mention}")


@bot.tree.command(name="autoreply", description="Add custom auto reply")
async def autoreply(interaction: discord.Interaction, trigger: str, response: str):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    autoreplies[trigger.lower()] = response
    save_replies(autoreplies)

    await interaction.response.send_message(
        f"Added reply: '{trigger}' → '{response}'"
    )


@bot.tree.command(name="listautoreplies", description="Show all auto replies")
async def listautoreplies(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    if not autoreplies:
        await interaction.response.send_message(
            "No auto replies setup."
        )
        return

    msg = "**Auto Replies:**\n"

    for trigger, reply in autoreplies.items():
        msg += f"• `{trigger}` → `{reply}`\n"

    await interaction.response.send_message(msg)


@bot.tree.command(name="removeautoreply", description="Remove an auto reply")
async def removeautoreply(interaction: discord.Interaction, trigger: str):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    trigger = trigger.lower()

    if trigger not in autoreplies:
        await interaction.response.send_message(
            "❌ Trigger not found."
        )
        return

    del autoreplies[trigger]
    save_replies(autoreplies)

    await interaction.response.send_message(
        f"✅ Removed auto reply for `{trigger}`"
    )


# ================= CREDITS AND GAMES =================

@bot.tree.command(name="setwinchance")
async def setwinchance(interaction: discord.Interaction, percent: int):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

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
    credits[user_id] = credits.get(user_id, 0)
    save_credits(credits)
    await interaction.response.send_message(f"💰 Balance: {credits[user_id]}")


@bot.tree.command(name="rigrocket")
async def rigrocket(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["rocket_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🚀 Rocket rig enabled.",
        ephemeral=True
    )


@bot.tree.command(name="unrigrocket")
async def unrigrocket(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["rocket_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Rocket normal mode.",
        ephemeral=True
    )


@bot.tree.command(name="rocket", description="Play Rocket")
async def rocket(interaction: discord.Interaction, bet: int, auto_cashout: float | None = None):
    user_id = str(interaction.user.id)
    credits[user_id] = credits.get(user_id, 0)

    if bet <= 0:
        await interaction.response.send_message("❌ Invalid bet.")
        return

    if credits[user_id] < bet:
        await interaction.response.send_message("❌ Not enough credits.")
        return

    if auto_cashout is not None and auto_cashout <= 1:
        await interaction.response.send_message("❌ Auto cashout must be above 1.00x.")
        return

    credits[user_id] -= bet
    save_credits(credits)

    view = RocketView(interaction.user, bet)

    embed = discord.Embed(
        title="🚀 Rocket Game",
        description="Multiplier: **1.00x**",
        color=discord.Color.blue(),
    )
    embed.set_image(url="https://media.tenor.com/CLHrRkRJZFIAAAAi/snoopy-aviator-aviation.gif")

    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()

    roll = random.randint(1, 100)
    if game_settings.get("rocket_rigged", False):
        crash_point = round(random.uniform(1.00, 1.30), 2)
    elif roll > game_settings.get("global_win_chance", 20):
        crash_point = round(random.uniform(1.00, 2.50), 2)
    else:
        crash_point = round(random.uniform(3.00, 15.00), 2)

    while not view.crashed and not view.cashed_out:
        await asyncio.sleep(1)
        view.multiplier += 0.25

        if auto_cashout is not None and view.multiplier >= auto_cashout:
            view.cashed_out = True
            winnings = int(bet * view.multiplier)
            credits[user_id] += winnings
            save_credits(credits)

            auto_embed = discord.Embed(
                title="💰 Auto Cashed Out!",
                description=f"Auto cashed out at **{view.multiplier:.2f}x**\nYou won {winnings} credits!",
                color=discord.Color.gold(),
            )
            auto_embed.set_image(url="https://media.tenor.com/CLHrRkRJZFIAAAAi/snoopy-aviator-aviation.gif")
            await msg.edit(embed=auto_embed, view=None)
            return

        if view.multiplier >= crash_point:
            view.crashed = True
            crash_embed = discord.Embed(
                title="💥 Rocket Crashed!",
                description=f"Crashed at **{view.multiplier:.2f}x**\nYou lost {bet} credits.",
                color=discord.Color.red(),
            )
            crash_embed.set_image(url="https://media.tenor.com/QnZrplecSiQAAAAC/explosion-bear-grylls.gif")
            await msg.edit(embed=crash_embed, view=None)
            return

        live_embed = discord.Embed(
            title="🚀 Rocket Flying",
            description=f"Multiplier: **{view.multiplier:.2f}x**",
            color=discord.Color.green(),
        )
        live_embed.set_image(url="https://media.tenor.com/CLHrRkRJZFIAAAAi/snoopy-aviator-aviation.gif")
        await msg.edit(embed=live_embed, view=view)


@bot.tree.command(name="addcredits", description="Add credits to a user")
async def addcredits(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    user_id = str(member.id)

    credits[user_id] = credits.get(user_id, 0) + amount

    save_credits(credits)

    await interaction.response.send_message(
        f"✅ Added {amount} credits to {member.mention}",
        ephemeral=True
    )


@bot.tree.command(name="plinko")
async def plinko(interaction: discord.Interaction, bet: int):

    user_id = str(interaction.user.id)

    credits[user_id] = credits.get(user_id, 0)

    if credits[user_id] < bet:
        await interaction.response.send_message(
            "❌ Not enough credits."
        )
        return

    credits[user_id] -= bet

    multipliers = [0.2, 0.5, 0.8, 1.2, 2, 5, 10]
    weights = [30, 25, 20, 15, 7, 2, 1]

    if game_settings.get("plinko_rigged", False):
        multiplier = random.choice([0.2, 0.5])
    else:
        multiplier = random.choices(
            multipliers,
            weights=weights
        )[0]

    winnings = int(bet * multiplier)

    credits[user_id] += winnings

    save_credits(credits)

    embed = discord.Embed(
        title="🎯 Plinko",
        description=(
            f"Bet: {bet}\n"
            f"Multiplier: {multiplier}x\n"
            f"Won: {winnings}"
        ),
        color=discord.Color.green()
    )

    await interaction.response.send_message(
        embed=embed
    )


# ================= MAYOR BATTLE AND TICKETS =================

BATTLE_ROLE_ID = 1505504246894956604

SUPPORT_CATEGORY_ID = 1504815315425431552
REGISTRATION_CATEGORY_ID = 1504815436082970624
REWARD_CATEGORY_ID = 1504815588709498900

SUPPORT_PING_ROLE = 1504816008349749368
REGISTRATION_PING_ROLE = 1505504246894956604
REWARD_PING_ROLE = 1504816008349749368

PANEL_CHANNEL_ID = 1504813235050647613
BATTLE_EMOJI = "💖"


def has_role(member, role_id):
    return any(role.id == role_id for role in getattr(member, "roles", []))


@bot.tree.command(name="setemoji")
async def setemoji(interaction: discord.Interaction, emoji: str):
    global BATTLE_EMOJI

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    BATTLE_EMOJI = emoji
    await interaction.response.send_message(f"✅ Emoji changed to {emoji}", ephemeral=True)


@bot.tree.command(name="mayorbattle")
async def mayorbattle(
    interaction: discord.Interaction,
    leader: discord.Member,
    staff1: discord.Member,
    staff2: discord.Member,
    staff3: discord.Member,
    number: str,
):
    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    embed = discord.Embed(
        title="👑 MAYOR BATTLE REGISTRATION",
        description=(
            f"👑 **Leader:** {leader.mention}\n\n"
            f"🛡️ **Staff 1:** {staff1.mention}\n\n"
            f"🛡️ **Staff 2:** {staff2.mention}\n\n"
            f"🛡️ **Staff 3:** {staff3.mention}\n\n"
            f"📞 **Number:** `{number}`"
        ),
        color=discord.Color.gold(),
    )
    embed.set_image(
        url="https://images-ext-1.discordapp.net/external/XM6Rq2OqezDS1x7DYxvBzwDTs2ZsLxzDDxfqadnecRo/%3Fsize%3D2048/https/cdn.discordapp.com/icons/1423469936566730907/a_483a8949102d09f167c7435d0a48b269.gif?width=288&height=288"
    )
    embed.set_footer(text="👑 Prepare For Mayor Battle 👑")

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction(BATTLE_EMOJI)
    await interaction.response.send_message("✅ Mayor battle panel created.", ephemeral=True)


@bot.tree.command(name="form")
async def form(interaction: discord.Interaction):
    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📋 MAYOR BATTLE FORM",
        description="**Leader :-**\n\n**Staff 1 :-**\n\n**Staff 2 :-**\n\n**Staff 3 :-**\n\n**Number :-**",
        color=discord.Color.gold(),
    )
    embed.set_footer(text="Fill The Form Properly")
    await interaction.response.send_message(embed=embed)


class DeleteTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Delete Ticket", style=discord.ButtonStyle.red, emoji="🗑️", custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = discord.utils.get(interaction.guild.roles, id=SUPPORT_PING_ROLE)
        if support_role not in interaction.user.roles:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ Deleting ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, emoji="✅", custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = discord.utils.get(interaction.guild.roles, id=SUPPORT_PING_ROLE)
        if support_role not in interaction.user.roles:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        embed = discord.Embed(
            title="✅ Ticket Claimed",
            description=f"{interaction.user.mention} claimed this ticket.",
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Ticket claimed.", ephemeral=True)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.blurple, emoji="📄", custom_id="transcript_ticket")
    async def transcript_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        messages = []
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            content = msg.content or ""
            messages.append(f"{msg.author}: {content}")

        transcript = "\n".join(messages) or "No text messages found."
        file = discord.File(fp=io.StringIO(transcript), filename="transcript.txt")

        try:
            await interaction.user.send("📄 Ticket Transcript", file=file)
            await interaction.response.send_message("✅ Transcript sent in DM.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Your DMs are closed.", ephemeral=True)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        support_role = discord.utils.get(interaction.guild.roles, id=SUPPORT_PING_ROLE)
        if support_role not in interaction.user.roles:
            await interaction.response.send_message("❌ No permission.", ephemeral=True)
            return

        ticket_user = None
        for target in interaction.channel.overwrites:
            if isinstance(target, discord.Member) and target != interaction.guild.me:
                ticket_user = target
                break

        if ticket_user:
            await interaction.channel.set_permissions(ticket_user, view_channel=False)
            await interaction.channel.edit(name=f"closed-{ticket_user.name}")

        close_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description="User can no longer see this ticket.\n\nStaff may now choose to delete it.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=close_embed, view=DeleteTicketView())


class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction, category_id, role_id, prefix):
        guild = interaction.guild
        category = guild.get_channel(category_id)
        role = guild.get_role(role_id)

        if category is None or role is None:
            await interaction.response.send_message("❌ Ticket setup is missing a category or role.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=f"{prefix}-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
        )

        await channel.send(
            f"{interaction.user.mention} {role.mention}\n\n✅ Staff will reach out to you soon.",
            view=TicketControls(),
        )
        await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.blurple, emoji="💖", custom_id="support_ticket")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, SUPPORT_CATEGORY_ID, SUPPORT_PING_ROLE, "support")

    @discord.ui.button(label="Reward Claim", style=discord.ButtonStyle.green, emoji="🎁", custom_id="reward_ticket")
    async def reward_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, REWARD_CATEGORY_ID, REWARD_PING_ROLE, "reward")

    @discord.ui.button(label="Registration", style=discord.ButtonStyle.red, emoji="📋", custom_id="registration_ticket")
    async def registration_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, REGISTRATION_CATEGORY_ID, REGISTRATION_PING_ROLE, "registration")


@bot.tree.command(name="sendpanel")
async def sendpanel(interaction: discord.Interaction):
    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message("❌ No permission.", ephemeral=True)
        return

    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel is None:
        await interaction.response.send_message("❌ Panel channel not found.", ephemeral=True)
        return

    embed = discord.Embed(
        title="💖 Server Support",
        description="Click a button below to open a ticket.\n\n📋 Registration\n🎁 Reward Claim\n💖 Contact Support",
        color=discord.Color.purple(),
    )
    await channel.send(embed=embed, view=SupportPanel())
    await interaction.response.send_message("✅ Support panel sent.", ephemeral=True)


# ================= STATS SYSTEM =================

DB = "stats.db"
voice_times = {}


async def setup_stats_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id INTEGER PRIMARY KEY,
                messages INTEGER DEFAULT 0,
                daily_messages INTEGER DEFAULT 0,
                voice_seconds INTEGER DEFAULT 0,
                daily_voice_seconds INTEGER DEFAULT 0
            )
            """
        )
        await db.commit()


async def ensure_user(user_id):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO user_stats(user_id) VALUES(?)", (user_id,))
        await db.commit()


@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if before.channel is None and after.channel is not None:
        voice_times[member.id] = datetime.now(timezone.utc)
        return

    if before.channel is not None and after.channel is None and member.id in voice_times:
        join_time = voice_times.pop(member.id)
        total_seconds = int((datetime.now(timezone.utc) - join_time).total_seconds())

        await ensure_user(member.id)
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                """
                UPDATE user_stats
                SET voice_seconds = voice_seconds + ?,
                    daily_voice_seconds = daily_voice_seconds + ?
                WHERE user_id = ?
                """,
                (total_seconds, total_seconds, member.id),
            )
            await db.commit()


@tasks.loop(hours=24)
async def reset_daily_stats():
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE user_stats SET daily_messages = 0, daily_voice_seconds = 0")
        await db.commit()


async def create_stats_image(member, messages, voice_seconds):
    width = 900
    height = 350
    img = Image.new("RGB", (width, height), (20, 20, 30))
    draw = ImageDraw.Draw(img)

    font_big = ImageFont.load_default()
    font_small = ImageFont.load_default()

    avatar_bytes = await member.display_avatar.with_size(256).read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((150, 150))
    img.paste(avatar, (40, 80))

    draw.text((240, 50), member.name, fill="white", font=font_big)
    draw.rectangle((240, 120, 500, 220), fill=(40, 40, 50))
    draw.text((270, 150), f"Messages: {messages}", fill="white", font=font_small)

    hours = round(voice_seconds / 3600, 2)
    draw.rectangle((550, 120, 810, 220), fill=(40, 40, 50))
    draw.text((580, 150), f"Voice: {hours} Hours", fill="white", font=font_small)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


@bot.command()
async def stats(ctx, member: discord.Member | None = None):
    member = member or ctx.author
    await ensure_user(member.id)

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "SELECT messages, voice_seconds FROM user_stats WHERE user_id = ?",
            (member.id,),
        )
        data = await cursor.fetchone()

    image = await create_stats_image(member, data[0], data[1])
    await ctx.send(file=discord.File(image, filename=f"stats_{member.id}.png"))


@bot.command(name="s,t")
async def text_stats(ctx):
    await ensure_user(ctx.author.id)

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT messages FROM user_stats WHERE user_id = ?", (ctx.author.id,))
        data = await cursor.fetchone()

    await ctx.send(f"📨 {ctx.author.mention} Total Messages: **{data[0]}**")


@bot.command(name="s,v")
async def voice_stats(ctx):
    await ensure_user(ctx.author.id)

    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute("SELECT voice_seconds FROM user_stats WHERE user_id = ?", (ctx.author.id,))
        data = await cursor.fetchone()

    hours = round(data[0] / 3600, 2)
    await ctx.send(f"🎤 {ctx.author.mention} Voice Time: **{hours} Hours**")


@bot.command()
async def leaderboard(ctx, category=None):
    if category not in ["msg", "voice"]:
        await ctx.send("Use:\n`,leaderboard msg`\n`,leaderboard voice`")
        return

    async with aiosqlite.connect(DB) as db:
        if category == "msg":
            cursor = await db.execute(
                "SELECT user_id, messages FROM user_stats ORDER BY messages DESC LIMIT 10"
            )
            data = await cursor.fetchall()
            text = "**🏆 Message Leaderboard**\n\n"
            for i, row in enumerate(data, start=1):
                user = await bot.fetch_user(row[0])
                text += f"{i}. {user.name} — {row[1]} msgs\n"
        else:
            cursor = await db.execute(
                "SELECT user_id, voice_seconds FROM user_stats ORDER BY voice_seconds DESC LIMIT 10"
            )
            data = await cursor.fetchall()
            text = "**🎤 Voice Leaderboard**\n\n"
            for i, row in enumerate(data, start=1):
                user = await bot.fetch_user(row[0])
                hours = round(row[1] / 3600, 2)
                text += f"{i}. {user.name} — {hours}h\n"

    await ctx.send(text)


@bot.command()
async def dailyleaderboard(ctx, category=None):
    if category not in ["msg", "voice"]:
        await ctx.send("Use:\n`,dailyleaderboard msg`\n`,dailyleaderboard voice`")
        return

    async with aiosqlite.connect(DB) as db:
        if category == "msg":
            cursor = await db.execute(
                "SELECT user_id, daily_messages FROM user_stats ORDER BY daily_messages DESC LIMIT 10"
            )
            data = await cursor.fetchall()
            text = "**📅 Daily Message Leaderboard**\n\n"
            for i, row in enumerate(data, start=1):
                user = await bot.fetch_user(row[0])
                text += f"{i}. {user.name} — {row[1]} msgs\n"
        else:
            cursor = await db.execute(
                "SELECT user_id, daily_voice_seconds FROM user_stats ORDER BY daily_voice_seconds DESC LIMIT 10"
            )
            data = await cursor.fetchall()
            text = "**📅 Daily Voice Leaderboard**\n\n"
            for i, row in enumerate(data, start=1):
                user = await bot.fetch_user(row[0])
                hours = round(row[1] / 3600, 2)
                text += f"{i}. {user.name} — {hours}h\n"

    await ctx.send(text)


@bot.command()
async def fixdb(ctx):
    await setup_stats_db()
    await ctx.send("Database fixed.")


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.lower()
    for trigger, reply in autoreplies.items():
        if trigger in content:
            await message.channel.send(reply)
            break

    try:
        await ensure_user(message.author.id)
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                """
                UPDATE user_stats
                SET messages = messages + 1,
                    daily_messages = daily_messages + 1
                WHERE user_id = ?
                """,
                (message.author.id,),
            )
            await db.commit()
    except Exception as e:
        print(e)

    await bot.process_commands(message)

@bot.event
async def on_wavelink_track_end(payload):
    player = payload.player

    if not player.queue.is_empty:
        next_track = player.queue.get()
        await player.play(next_track)

@bot.tree.command(name="limbo", description="Play Limbo")
async def limbo(interaction: discord.Interaction, bet: int, target: float):
    user_id = str(interaction.user.id)

    credits[user_id] = credits.get(user_id, 0)

    if bet <= 0:
        await interaction.response.send_message("❌ Invalid bet.")
        return

    if target < 1.01:
        await interaction.response.send_message("❌ Minimum target is 1.01x")
        return

    if credits[user_id] < bet:
        await interaction.response.send_message("❌ Not enough credits.")
        return

    credits[user_id] -= bet

    roll = round(random.uniform(1.00, 10.00), 2)

    if roll >= target:
        winnings = int(bet * target)
        credits[user_id] += winnings

        embed = discord.Embed(
            title="🎯 Limbo Win!",
            description=(
                f"Target: **{target}x**\n"
                f"Rolled: **{roll}x**\n\n"
                f"💰 Won: {winnings} credits"
            ),
            color=discord.Color.green(),
        )
    else:
        embed = discord.Embed(
            title="💀 Limbo Lose",
            description=(
                f"Target: **{target}x**\n"
                f"Rolled: **{roll}x**\n\n"
                f"❌ Lost: {bet} credits"
            ),
            color=discord.Color.red(),
        )

    save_credits(credits)

    await interaction.response.send_message(embed=embed)

class MinesView(discord.ui.View):
    def __init__(self, user, bet):
        super().__init__(timeout=60)

        self.user = user
        self.bet = bet
        self.safe_tiles = 0

        self.mine_position = random.randint(0, 8)

        for i in range(9):
            self.add_item(MineButton(i))

    async def explode(self, interaction, button):
        for item in self.children:
            item.disabled = True

            if isinstance(item, MineButton):
                if item.position == self.mine_position:
                    item.label = "💣"
                else:
                    item.label = "💎"

        embed = discord.Embed(
            title="💥 You Hit A Mine!",
            description=f"Lost {self.bet} credits.",
            color=discord.Color.red(),
        )

        await interaction.response.edit_message(embed=embed, view=self)

    async def safe_pick(self, interaction, button):
        self.safe_tiles += 1

        multiplier = round(1 + (self.safe_tiles * 0.4), 2)

        winnings = int(self.bet * multiplier)

        embed = discord.Embed(
            title="💎 Safe Tile!",
            description=(
                f"Safe Picks: **{self.safe_tiles}**\n"
                f"Multiplier: **{multiplier}x**\n"
                f"Cashout Value: **{winnings}**"
            ),
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=self)

class MineButton(discord.ui.Button):
    def __init__(self, position):
        super().__init__(
            label="❓",
            style=discord.ButtonStyle.secondary,
            row=position // 3
        )

        self.position = position

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view

        if interaction.user != view.user:
            await interaction.response.send_message(
                "❌ This isn't your game.",
                ephemeral=True
            )
            return

        self.disabled = True

        if self.position == view.mine_position:
            self.style = discord.ButtonStyle.danger
            await view.explode(interaction, self)
        else:
            self.style = discord.ButtonStyle.success
            self.label = "💎"

            await view.safe_pick(interaction, self)

@bot.tree.command(name="mines", description="Play Mines")
async def mines(interaction: discord.Interaction, bet: int):
    user_id = str(interaction.user.id)

    credits[user_id] = credits.get(user_id, 0)

    if bet <= 0:
        await interaction.response.send_message("❌ Invalid bet.")
        return

    if credits[user_id] < bet:
        await interaction.response.send_message("❌ Not enough credits.")
        return

    credits[user_id] -= bet
    save_credits(credits)

    embed = discord.Embed(
        title="💣 Mines",
        description="Pick a tile!",
        color=discord.Color.orange(),
    )

    await interaction.response.send_message(
        embed=embed,
        view=MinesView(interaction.user, bet)
    )

@bot.tree.command(name="rigplinko")
async def rigplinko(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["plinko_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🎯 Plinko rig enabled.",
        ephemeral=True
    )


@bot.tree.command(name="unrigplinko")
async def unrigplinko(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["plinko_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Plinko normal mode.",
        ephemeral=True
    )

@bot.tree.command(name="rigmines")
async def rigmines(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["mines_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "💣 Mines rig enabled.",
        ephemeral=True
    )


@bot.tree.command(name="unrigmines")
async def unrigmines(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["mines_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Mines normal mode.",
        ephemeral=True
    )

@bot.tree.command(name="riglimbo")
async def riglimbo(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["limbo_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🎯 Limbo rig enabled.",
        ephemeral=True
    )


@bot.tree.command(name="unriglimbo")
async def unriglimbo(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["limbo_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Limbo normal mode.",
        ephemeral=True
    )

@bot.tree.command(name="rigplinko")
async def rigplinko(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["plinko_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🎯 Plinko rig enabled.",
        ephemeral=True
    )

@bot.tree.command(name="unrigplinko")
async def unrigplinko(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["plinko_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Plinko normal mode.",
        ephemeral=True
    )

@bot.tree.command(name="rigmines")
async def rigmines(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["mines_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "💣 Mines rig enabled.",
        ephemeral=True
    )

@bot.tree.command(name="unrigmines")
async def unrigmines(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["mines_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Mines normal mode.",
        ephemeral=True
    )

@bot.tree.command(name="riglimbo")
async def riglimbo(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["limbo_rigged"] = True
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "🎯 Limbo rig enabled.",
        ephemeral=True
    )

@bot.tree.command(name="unriglimbo")
async def unriglimbo(interaction: discord.Interaction):

    if not has_role(interaction.user, BATTLE_ROLE_ID):
        await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )
        return

    game_settings["limbo_rigged"] = False
    save_game_settings(game_settings)

    await interaction.response.send_message(
        "✅ Limbo normal mode.",
        ephemeral=True
    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    bot.add_view(SupportPanel())
    bot.add_view(TicketControls())
    bot.add_view(DeleteTicketView())

    try:
        node = wavelink.Node(
            uri=os.getenv("LAVALINK_URI", "https://my-lavalink-m9vr.onrender.com"),
            password=os.getenv("LAVALINK_PASSWORD", "mypassword"),
        )
        await wavelink.Pool.connect(client=bot, nodes=[node])
        print("✅ Lavalink Connected")
    except Exception as e:
        print(f"Lavalink Error: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

    await setup_stats_db()

    if not reset_daily_stats.is_running():
        reset_daily_stats.start()

    print("✅ Bot Fully Ready")


token = os.getenv("TOKEN")
if not token:
    raise RuntimeError("TOKEN environment variable is missing.")

bot.run(token)
