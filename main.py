import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# --- ここを修正しました ---
intents = discord.Intents.default()
intents.message_content = True  # 警告を消すための設定
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"ログインしました: {bot.user}")


# --- モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    message_input = discord.ui.TextInput(
        label="手紙の中身",
        style=discord.TextStyle.long,
        placeholder="ここに伝えたい想いを入力してください...",
        required=True,
        max_length=1000
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            message_text = self.message_input.value
            file_data = io.BytesIO(message_text.encode('utf-8'))
            discord_file = discord.File(file_data, filename="想い.txt")
            
            await self.target_user.send(
                content="📩 あなたへ匿名の想いが届いています。ファイルを開いて読んでください。", 
                file=discord_file
            )
            await interaction.followup.send("想いをファイルにして届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("相手のDMが閉じられているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send("送信中にエラーが発生しました。", ephemeral=True)


# --- スラッシュコマンドの設定 ---
@bot.tree.command(name="貴方に", description="匿名の手紙（txtファイル）を相手のDMに届けます")
@app_commands.describe(相手="メッセージを送りたい相手を選んでください")
async def send_anonymous_file(interaction: discord.Interaction, 相手: discord.User):
    await interaction.response.send_modal(MessageModal(target_user=相手))


# 安全にトークンを読み込んで起動
bot.run(TOKEN)
