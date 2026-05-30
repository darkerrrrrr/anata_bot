import os
import discord
from discord import app_commands
from discord.ext import commands
import io
import asyncio
# 💡 分割した「返信機能付き」のボタン画面をここから綺麗に読み込みます
from reply_system import SelectModeView

# ─── Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


# 🚀 /send コマンドの登録
@bot.tree.command(name="send", description="指定したユーザーのDMにメッセージ（テキストファイル）を送信します")
async def send_command(interaction: discord.Interaction):
    # 💡 読み込んだ返信機能付きのViewをセットして送信します
    await interaction.response.send_message(
        "送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )


# 🛠️ !msgdel テキストコマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """過去ログからこのBotのメッセージを全消去し、権限があればコマンド文字も無言で削除します"""
    
    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

    try:
        await ctx.message.delete()
    except discord.DiscordException:
        pass


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
