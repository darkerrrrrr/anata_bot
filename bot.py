import os
import discord
from discord import app_commands
from discord.ext import commands, tasks  # 💡 サーバー数を定期的に数えて更新するために tasks を追加
import io
import asyncio
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


# 💡 【新機能：アクティビティ自動更新システム】
# 10分ごとに現在導入されているサーバーの総数を数え直し、Botのステータス画面を更新します
@tasks.loop(minutes=10)
async def update_activity():
    await bot.wait_until_ready()
    # 導入されているサーバーの数を取得
    server_count = len(bot.guilds)
    
    # 🔍 【表示形式の設定】
    # 例：「3個のサーバーで稼働中」とプロフィールに表示されます
    activity_text = f"{server_count}個のサーバーで稼働中"
    
    # カスタムステータスとしてBotのアクティビティを設定
    await bot.change_presence(
        activity=discord.CustomActivity(name=activity_text)
    )

# Botの起動が完了した瞬間に、上記のアクティビティ更新システムを裏側でスタートさせます
@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")
    if not update_activity.is_running():
        update_activity.start()


# 🚀 /send コマンドの登録
@bot.tree.command(name="send", description="指定したユーザーのDMにメッセージ（テキストファイル）を送信します")
async def send_command(interaction: discord.Interaction):
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


TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
