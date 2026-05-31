import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
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


# 💡 【アクティビティ固定表示システム】
# 10分ごとにステータスをチェックし、指定された文字列を常に常駐表示します
@tasks.loop(minutes=10)
async def update_activity():
    await bot.wait_until_ready()
    
    # 🔍 【表示文面の設定】
    # ご指定通り「darker_daysが作成」という親しみやすい形に固定しました
    activity_text = "darker_daysが作成"
    
    # カスタムステータスとしてBotのプロフィールに反映
    await bot.change_presence(
        activity=discord.CustomActivity(name=activity_text)
    )


# 💡 【サーバー導入時のDM通知システム】
# このBotがどこかのサーバーに新しく追加された瞬間に自動で発動し、あなただけに届きます
@bot.event
async def on_guild_join(guild: discord.Guild):
    if bot.application is None:
        await bot.application_info()
    
    owner = bot.application.owner
    if owner:
        try:
            notification_text = (
                f"🎉 **【Bot新規導入のお知らせ】**\n"
                f"新しいサーバーにBotが招待されました！\n\n"
                f"🏰 **サーバー名:** {guild.name}\n"
                f"🆔 **サーバーID:** {guild.id}\n"
                f"👥 **メンバー数:** {guild.member_count}人"
            )
            await owner.send(content=notification_text)
        except Exception:
            pass


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")
    # 起動した瞬間にアクティビティのループ処理を開始
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
