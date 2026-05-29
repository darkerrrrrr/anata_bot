import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import signal
import asyncio
import config

TOKEN = os.getenv("DISCORD_TOKEN")

# 💡 【バラバラを防ぐ修正】config.py側で定義されたインテント設定を正しく受け取ります
intents = config.intents

bot = commands.Bot(command_prefix="!", intents=intents)

class LetterModal(ui.Modal):
    def __init__(self, target_user: discord.User):
        super().__init__(title=f"{target_user.name} への手紙")
        self.target_user = target_user

        self.target_name_input = ui.TextInput(label="相手のなまえ", placeholder="例：〇〇さん", required=True, max_length=20)
        self.sender_name_input = ui.TextInput(label="あなたのなまえ（空欄で匿名）", placeholder="例：△△", required=False, max_length=20)
        self.content_input = ui.TextInput(label="手紙の中身", placeholder="メッセージを入力...", style=discord.TextStyle.long, required=True, max_length=1000)

        self.add_item(self.target_name_input)
        self.add_item(self.sender_name_input)
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        target_name = self.target_name_input.value.strip()
        sender_name = self.sender_name_input.value.strip()
        content = self.content_input.value

        if not target_name.endswith("へ") and not target_name.endswith("へ "): target_name += " へ"
        if sender_name and not sender_name.endswith("より") and not sender_name.endswith("より "): sender_name += " より"

        lines = config.check_letter_length(content)
        if lines > 20:
            await interaction.followup.send(f"【便箋からはみ出しています】あと約 {lines - 20} 行分削ってください。", ephemeral=True)
            return

        # 💡 【結合の修正】config側の正しい関数名（generate_letter_pdf）で呼び出します
        pdf_buffer = config.generate_letter_pdf(target_name, sender_name, content)

        try:
            # 💡 正しい読み込み位置になったバッファを discord.File に渡して送信します
            file = discord.File(pdf_buffer, filename="letter.pdf")
            await self.target_user.send("貴方に、お手紙が届きました。", file=file)
            await interaction.followup.send(f"{self.target_user.name} さんに手紙を無事に届けました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("相手がDMをすべて閉鎖しているか、ブロックされています。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラー: {e}", ephemeral=True)

@bot.tree.command(name="貴方に", description="手紙（PDFファイル）を相手のDMに届けます。")
@app_commands.describe(target_username="手紙を届けたい相手の「ユーザー名（@から始まる英数字の名前）」")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def anata_ni(interaction: discord.Interaction, target_username: str):
    search_name = target_username.strip()
    if search_name.startswith("@"): search_name = search_name[1:]

    target_user = None

    if interaction.guild:
        target_user = interaction.guild.get_member_named(search_name)
    
    if not target_user:
        target_user = discord.utils.find(lambda u: u.name == search_name, bot.users)

    if not target_user:
        await interaction.response.send_message(
            f"ユーザー名「{search_name}」が見つかりませんでした。\n"
            "※表示名（ニックネーム）ではなく、固有の『ユーザー名』を入力してください。", 
            ephemeral=True
        )
        return

    if target_user.bot:
        await interaction.response.send_message("Botに手紙は送れません。", ephemeral=True)
        return

    await interaction.response.send_modal(LetterModal(target_user))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try: await bot.tree.sync()
    except Exception as e: print(f"Sync failed: {e}")

@bot.event
async def on_message(message):
    if message.author.bot: return
    if message.content.startswith("!purge"):
        if message.guild and (message.author.guild_permissions.manage_messages or message.author.id == bot.owner_id):
            deleted = 0
            async for msg in message.channel.history(limit=100):
                if msg.author == bot.user:
                    try: await msg.delete(); deleted += 1
                    except discord.HTTPException: pass
            await message.channel.send(f"メッセージを {deleted} 件削除しました。", delete_after=5)

async def shutdown(loop, signal_obj=None):
    await bot.close()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks: task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(loop, s)))
        except NotImplementedError: pass
    
    try:
        loop.run_until_complete(bot.start(TOKEN))
    except KeyboardInterrupt:
        loop.run_until_complete(shutdown(loop))
    finally:
        loop.close()
