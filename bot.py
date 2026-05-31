import os
import discord
from discord import app_commands
from discord.ext import commands
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


# 💡 【新機能：サーバー導入時のDM通知システム】
# このBotがどこかのサーバーに新しく追加された瞬間に自動で発動します
@bot.event
async def on_guild_join(guild: discord.Guild):
    # 💡 あなた（Botの作成者/オーナー）のDiscordアカウントを自動で特定します
    # これにより、コード内にあなたのIDを直接書き込まなくても、あなたのDMへ確実に届きます
    if bot.application is None:
        await bot.application_info()
    
    owner = bot.application.owner
    
    if owner:
        try:
            # あなたのDMへ送る通知メッセージの作成
            notification_text = (
                f"🎉 **【Bot新規導入のお知らせ】**\n"
                f"新しいサーバーにBotが招待されました！\n\n"
                f"🏰 **サーバー名:** {guild.name}\n"
                f"🆔 **サーバーID:** {guild.id}\n"
                f"👥 **メンバー数:** {guild.member_count}人"
            )
            # あなたのDMへ直接送信
            await owner.send(content=notification_text)
            print(f"オーナー（{owner.name}）への導入通知DMの送信に成功しました: {guild.name}")
        except discord.Forbidden:
            print(f"エラー：オーナーがDMを閉じているため通知を送れませんでした。")
        except Exception as e:
            print(f"通知DM送信中に予期せぬエラーが発生しました: {e}")


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")


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
