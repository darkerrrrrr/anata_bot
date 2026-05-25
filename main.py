import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# 環境変数の読み込み（PCローカルテスト用の.envと、GitHub Actionsの両方に対応）
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Botの初期設定
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.event
async def on_ready():
    # スラッシュコマンドをDiscord側に登録（同期）する
    await bot.tree.sync()
    print(f"ログインしました: {bot.user}")


# --- モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    # メッセージを入力するテキストエリア（長文対応・最大1000文字）
    message_input = discord.ui.TextInput(
        label="手紙の中身",
        style=discord.TextStyle.long,
        placeholder="ここに伝えたい想いを入力してください...",
        required=True,
        max_length=1000
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user  # 送り先の相手を記憶しておく

    # 送信ボタンが押された時の処理
    async def on_submit(self, interaction: discord.Interaction):
        # 応答の初期対応を遅延させる（送信処理に時間がかかった際のエラー防止）
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 1. 入力されたメッセージをtxtファイルのデータに変換する
            message_text = self.message_input.value
            file_data = io.BytesIO(message_text.encode('utf-8'))
            discord_file = discord.File(file_data, filename="想い.txt")
            
            # 2. 相手のDMにファイルを送信する
            await self.target_user.send(
                content="📩 あなたへ匿名の想いが届いています。ファイルを開いて読んでください。", 
                file=discord_file
            )
            
            # 3. 送った本人にだけ「送信成功」を伝える（他の人には見えません）
            await interaction.followup.send("想いをファイルにして届けました。", ephemeral=True)
            
        except discord.Forbidden:
            # 相手がDMを設定で閉じている場合のエラー
            await interaction.followup.send("相手のDMが閉じられているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            # その他のエラーが発生した場合
            await interaction.followup.send("送信中にエラーが発生しました。", ephemeral=True)


# --- スラッシュコマンドの設定 ---
@bot.tree.command(name="貴方に", description="匿名の手紙（txtファイル）を相手のDMに届けます")
@app_commands.describe(相手="メッセージを送りたい相手を選んでください")
async def send_anonymous_file(interaction: discord.Interaction, 相手: discord.User):
    # コマンドを実行したら、モーダルウィンドウ（入力フォーム）を表示する
    await interaction.response.send_modal(MessageModal(target_user=相手))


# 安全にトークンを読み込んで起動
bot.run(TOKEN)