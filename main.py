import os
import io
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# PDF作成、および文章を自動折り返しさせるためのライブラリ
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# 💡 【修正】!purge コマンドを正常に動かすために default ではなく all に変更
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # 💡 【修正】起動時の bot.tree.sync() はレートリミットの原因になるため削除しました
    print(f"ログインしました: {bot.user}")


# --- 💡 【追加】管理者が手動でスラッシュコマンドを同期するためのコマンド ---
# Botを導入後、一度だけチャット欄で「 !sync 」と発言すればコマンドが登録されます。
# 6時間ごとの自動再起動時に毎回同期されるのを防ぎます。
@bot.command(name="sync")
@commands.is_owner() # Botの作成者だけが実行できるように制限
async def sync_commands(ctx):
    await bot.tree.sync()
    await ctx.send("スラッシュコマンドの同期が完了しました！", delete_after=5)


# --- モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    message_input = discord.ui.TextInput(
        label="手紙の中身",
        style=discord.TextStyle.long,
        placeholder="ここに伝えたい想いを入力してください...",
        required=True,
        max_length=4000
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            message_text = self.message_input.value
            
            # --- 📄 PDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            
            # フォントファイルの場所を指定して登録
            font_path = os.path.join("font", "AkazukiPOP.ttf")
            pdfmetrics.registerFont(TTFont('Akazukin', font_path))
            
            # A4用紙の余白設定（上下左右に50ポイントの壁を作ります）
            doc = SimpleDocTemplate(
                pdf_buffer, 
                pagesize=A4,
                leftMargin=50,
                rightMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            # 手紙の文字スタイルを作成
            styles = getSampleStyleSheet()
            letter_style = ParagraphStyle(
                name='LetterStyle',
                fontName='Akazukin',
                fontSize=16,       # 文字の大きさ16pt
                leading=28,        # 行の間隔28pt
                textColor='black'  # 文字の色
            )
            
            # 入力された文章をPDF用のデータ（ストーリー）に変換していきます
            story = []
            
            # あなたが手動で入れた改行（\n）を保ちつつ、長い行は自動で折り返す処理
            for line in message_text.split('\n'):
                if line.strip() == "":
                    # 空行の場合はスペースを空ける
                    story.append(Spacer(1, 28))
                else:
                    # 文字がある行は、右端で自動折り返しする設定で追加
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, letter_style))
            
            # PDFの組み立て
            doc.build(story)
            
            pdf_buffer.seek(0)
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            # --- 📄 PDF作成ここまで ---
            
            # 相手のDMへ手紙を送信
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
        # 💡 【修正】原因不明のエラーが起きた際にログを追えるように print を追加
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


# 安全にトークンを読み込んで起動
bot.run(TOKEN)
