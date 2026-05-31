import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from reply_system import SelectModeView

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

@tasks.loop(minutes=10)
async def update_activity():
    await bot.wait_until_ready()
    activity_text = "作：@darker_days"
    await bot.change_presence(activity=discord.CustomActivity(name=activity_text))

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
                f"👥 **メンバー数:** {guild.member_count}人"
            )
            await owner.send(content=notification_text)
        except Exception:
            pass

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")
    if not update_activity.is_running():
        update_activity.start()

# 🚀 /send コマンドの登録（target引数を追加し、ユーザーインストールを完全許可）
@bot.tree.command(name="send", description="指定したユーザーのDMにメッセージ（テキストファイル）を送信します")
@app_commands.describe(target="手紙を届けたい相手ユーザーを選択（メンション）してください")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def send_command(interaction: discord.Interaction, target: discord.User):
    # 選択された相手のデータを、そのまま返信システムViewへ安全に引き渡します
    await interaction.response.send_message(
        f"**{target.display_name}** さんへの送信モードを選択してください：", 
        view=SelectModeView(target_user=target), 
        ephemeral=True
    )

@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
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
