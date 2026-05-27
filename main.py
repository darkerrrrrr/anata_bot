import os
import io
import discord
import signal
import asyncio
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# PDF作成、および文章を自動折り返しさせるためのライブラリ
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# !purge やメッセージ履歴を正常に読み込むため、すべてのIntentsを有効化
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 🟢 起動時の処理 ---
@bot.event
async def on_ready():
    # 🔴 起動完了時に、強制的にステータスを「取り込み中」に変更します
    await bot.change_presence(status=discord.Status.dnd)
    print(f"ログインしました: {bot.user}")


# --- 🛑 GitHub Actionsからの強制終了シグナルをキャッチして安全にログアウトする処理 ---
async def ask_exit():
    print("終了シグナルを受信しました。安全にシャットダウンします...")
    await bot.close()

@bot.event
async def setup_hook():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(ask_exit()))
        except NotImplementedError:
            pass


# --- ⚙️ スラッシュコマンド同期用（管理者が手動で実行） ---
@bot.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx):
    await bot.tree.sync()
    await ctx.send("スラッシュコマンドの同期が完了しました！", delete_after=5)


# --- 📝 PDFの背景に「便箋の罫線」を描画する関数 ---
def draw_letter_lines(canvas_obj, doc):
    canvas_obj.saveState()
    # 線の色を薄いセピア（グレーブラウン）に設定
    canvas_obj.setStrokeColorRGB(0.75, 0.72, 0.68)
    canvas_obj.setLineWidth(0.5)
    
    # 横向きA4の高さの中で、上部120ptから下部60ptまで22pt間隔で罫線を引く
    start_y = 475
    end_y = 60
    line_interval = 22  # 本文の leading と同じ幅
    
    current_y = start_y
    while current_y >= end_y:
        # 左右の余白の間に線を引く
        canvas_obj.line(50, current_y, doc.pagesize - 50, current_y)
        current_y -= line_interval
        
    canvas_obj.restoreState()


# --- 📄 モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    # 💡 【変更】題名から「相手の名前」に変更しました
    name_input = discord.ui.TextInput(
        label="相手のなまえ（呼び名）",
        style=discord.TextStyle.short,
        placeholder="例：〇〇へ、〇〇さんへ など（『へ』や『さん』は自動で付きます）",
        required=True,
        max_length=50
    )

    message_input = discord.ui.TextInput(
        label="手紙の中身",
        style=discord.TextStyle.long,
        placeholder="ここに伝えたい想いを入力してください...",
        required=True,
        max_length=2000
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 入力された「相手の名前」と「本文」をそれぞれ取得
            target_name = self.name_input.value
            message_text = self.message_input.value
            
            # もし入力された名前に「へ」や「さん」が含まれていなければ、自動で「へ」を付けます
            if not (target_name.endswith("へ") or target_name.endswith("さん") or target_name.endswith("くん") or target_name.endswith("ちゃん")):
                target_name = f"{target_name}へ"
            
            # --- PDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            
            # しっぽり明朝（通常版）のファイルパスを指定して登録
            font_path = os.path.join("font", "ShipporiMincho-Regular.ttf")
            pdfmetrics.registerFont(TTFont('ShipporiMincho', font_path))
            
            # A4用紙の余白設定（横向き）
            doc = SimpleDocTemplate(
                pdf_buffer, 
                pagesize=landscape(A4),
                leftMargin=50,
                rightMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            styles = getSampleStyleSheet()
            
            # 💡 【変更】宛名用の文字スタイル（左寄せ：alignment=0、サイズは本文と同じ16pt）
            name_style = ParagraphStyle(
                name='LetterNameStyle',
                fontName='ShipporiMincho',
                fontSize=16,
                leading=22,
                textColor='black',
                alignment=0  # 0 は「左揃え（Left）」の意味です
            )
            
            # 本文用のスタイル（しっぽり明朝・16pt）
            letter_style = ParagraphStyle(
                name='LetterStyle',
                fontName='ShipporiMincho',
                fontSize=16,
                leading=22,
                textColor='black'
            )
            
            # 日付（右寄せ）用のスタイル
            right_style = ParagraphStyle(
                name='LetterRightStyle',
                fontName='ShipporiMincho',
                fontSize=14,
                leading=22,
                textColor='black',
                alignment=2  # 右揃え
            )
            
            story = []
            
            # 💡 【変更】一番上に「相手の名前」を左寄せで配置し、下に1行分の空間を空けます
            safe_name = target_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe_name, name_style))
            story.append(Spacer(1, 22))  # 宛名と本文を区切る空間
            
            # 本文を1行ずつ追加していく処理
            for line in message_text.split('\n'):
                if line.strip() == "":
                    story.append(Spacer(1, 22))
                else:
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, letter_style))
            
            # シンプルに「日付だけ」を右下に配置します
            current_date = datetime.now().strftime("%Y年%m月%d日") [current_time];
            story.append(Spacer(1, 22))  # 本文との間の隙間
            story.append(Paragraph(f"{current_date}", right_style))
            
            # 背景に罫線を描画して組み立て
            doc.build(story, onFirstPage=draw_letter_lines, onLaterPages=draw_letter_lines)
            
            pdf_buffer.seek(0)
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            # --- PDF作成ここまで ---
            
            await self.target_user.send(
                content="📩 あなたへ匿名の想いが届いています。PDFファイルを開いて読んでください。", 
                file=discord_file
            )
            await interaction.followup.send("想いをPDFファイルにして届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("相手のDMが閉じられているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            print(f"PDF作成エラー: {e}")
            await interaction.followup.send(f"送信中にエラーが発生しました。理由: {e}", ephemeral=True)


# --- 💬 スラッシュコマンドの設定 ---
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
        print(f"ユーザー取得エラー: {e}")
        await interaction.response.send_message(f"ユーザーの取得中にエラーが発生しました。理由: {e}", ephemeral=True)


# --- 🧹 !purge コマンドの設定 ---
@bot.command(name="purge")
async def purge_messages(ctx, limit: int = 100):
    deleted_count = 0
    try:
        async for message in ctx.channel.history(limit=limit):
            if message.author == bot.user:
                await message.delete()
                deleted_count += 1
        await ctx.send(f"Botのメッセージを {deleted_count} 件削除しました。", delete_after=5)
    except discord.Forbidden:
        await ctx.send("メッセージを削除する権限がありませんでした。", delete_after=5)
    except Exception as e:
        await ctx.send(f"削除中にエラーが発生しました: {e}", delete_after=5)


bot.run(TOKEN)
