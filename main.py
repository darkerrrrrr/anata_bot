import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# PDF作成用のライブラリ
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 🔄 送信したメッセージの情報を一時的に保存するメモリ（辞書）
# 構造: { あなたのユーザーID: [相手のDMに送ったメッセージオブジェクトのリスト] }
sent_messages_cache = {}

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

    def __init__(self, target_user: discord.User, sender_id: int):
        super().__init__()
        self.target_user = target_user
        self.sender_id = sender_id  # 送信者のIDを記録

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            message_text = self.message_input.value
            
            # --- 📄 PDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            p = canvas.Canvas(pdf_buffer, pagesize=A4)
            width, height = A4
            
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            p.setFont('HeiseiMin-W3', 14) # 文字サイズ14pt
            
            x = 50
            y = height - 80
            line_height = 24
            
            for line in message_text.split('\n'):
                if y < 50:
                    p.showPage()
                    p.setFont('HeiseiMin-W3', 14)
                    y = height - 80
                p.drawString(x, y, line)
                y -= line_height
            
            p.showPage()
            p.save()
            pdf_buffer.seek(0)
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            # --- 📄 PDF作成ここまで ---
            
            # 相手のDMへ手紙を送信し、送信された「メッセージの情報」を変数に保存します
            sent_message = await self.target_user.send(
                content="📩 あなたへ匿名の想いが届いています。PDFファイルを開いて読んでください。", 
                file=discord_file
            )
            
            # 💡 送信したメッセージの情報をあなたのIDと紐づけてメモリに保存します
            if self.sender_id not in sent_messages_cache:
                sent_messages_cache[self.sender_id] = []
            sent_messages_cache[self.sender_id].append(sent_message)
            
            await interaction.followup.send("想いをPDFファイルにして届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("相手のDMが閉じられているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            print(f"PDF作成エラー: {e}")
            await interaction.followup.send("送信中にエラーが発生しました。", ephemeral=True)


# --- スラッシュコマンドの設定 ---
@bot.tree.command(name="貴方に", description="匿名の手紙（PDFファイル）を相手のDMに届けます")
@app_commands.describe(相手のid="想いを届けたい相手のユーザーID（数字の羅列）を貼り付けてください")
async def send_anonymous_file(interaction: discord.Interaction, 相手のid: str):
    
    if not 相手のid.isdigit():
        await interaction.response.send_message("【エラー】ユーザーIDは数字だけで入力してください。", ephemeral=True)
        return

    try:
        target_user = await bot.fetch_user(int(相手のid))
        # モーダルを開く際に、あなたのID（interaction.user.id）も一緒に渡します
        await interaction.response.send_modal(MessageModal(target_user=target_user, sender_id=interaction.user.id))
        
    except discord.NotFound:
        await interaction.response.send_message("【エラー】そのIDのユーザーが見つかりませんでした。数字を確認してください。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("ユーザーの取得中にエラーが発生しました。", ephemeral=True)


# --- 🧹 !purge コマンドの設定（メッセージ削除機能） ---
@bot.command(name="purge")
async def purge_messages(ctx):
    # コマンドを実行した人（あなた）が過去に送ったメッセージのリストを取得
    user_id = ctx.author.id
    
    if user_id not in sent_messages_cache or len(sent_messages_cache[user_id]) == 0:
        await ctx.send("取り消せるメッセージ（手紙）がありません。", delete_after=5)
        return
    
    deleted_count = 0
    # あなたが過去に送った手紙をループで1つずつ削除していく
    for message in sent_messages_cache[user_id]:
        try:
            await message.delete() # 相手のDM画面からメッセージとPDFを削除
            deleted_count += 1
        except Exception as e:
            print(f"メッセージ削除失敗: {e}")
            
    # 削除が終わったらメモリを空にする
    sent_messages_cache[user_id] = []
    
    await ctx.send(f"あなたが送信した手紙（{deleted_count}件）を相手のDMからすべて取り消しました。", delete_after=5)


bot.run(TOKEN)
