import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# PDF作成とフォント登録のためのライブラリ
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
            
            # --- 📄 ここから綺麗なPDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            
            # A4サイズの縦向きでPDFを作成
            p = canvas.Canvas(pdf_buffer, pagesize=A4)
            width, height = A4
            
            # 🖋️ 日本語の綺麗で上品なフォント（HeiseiMin-W3: 平成明朝体）を登録して使用
            # 相手のスマホやPCでも必ずきれいに表示される標準のフォントです
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            p.setFont('HeiseiMin-W3', 14) # フォント名と文字の大きさ(14pt)を指定
            
            # 文章の書き出し位置（左上の余白設定）
            x = 50
            y = height - 80
            line_height = 24  # 改行したときの行の間隔
            
            # 入力された文章を改行ごとに分けて、1行ずつPDFに書き込む
            for line in message_text.split('\n'):
                # 画面の下までいったら新しいページを作成する（長文対策）
                if y < 50:
                    p.showPage()
                    p.setFont('HeiseiMin-W3', 14)
                    y = height - 80
                
                p.drawString(x, y, line)
                y -= line_height # 次の行のために位置を下げる
            
            # PDFの編集を終了して保存
            p.showPage()
            p.save()
            
            # 作成したPDFデータをDiscordで送れるファイル形式に変換
            pdf_buffer.seek(0)
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            # --- 📄 PDF作成処理ここまで ---
            
            # 相手のDMへ送信
            await self.target_user.send(
                content="📩 あなたへ匿名の想いが届いています。PDFファイルを開いて読んでください。", 
                file=discord_file
            )
            await interaction.followup.send("想いを綺麗なPDFファイルにして届けました。", ephemeral=True)
            
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
        await interaction.response.send_modal(MessageModal(target_user=target_user))
        
    except discord.NotFound:
        await interaction.response.send_message("【エラー】そのIDのユーザーが見つかりませんでした。数字を確認してください。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message("ユーザーの取得中にエラーが発生しました。", ephemeral=True)


bot.run(TOKEN)
