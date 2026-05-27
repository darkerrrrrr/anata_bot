import os
import io
import discord
import signal
import asyncio
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


# --- 📄 モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    # 💡 【新機能】手紙の題名（タイトル）を入力する欄を追加しました
    title_input = discord.ui.TextInput(
        label="手紙の題名（タイトル）",
        style=discord.TextStyle.short,
        placeholder="例：ありがとう、お祝い、伝えたいこと など",
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
            # 入力された「題名」と「本文」をそれぞれ取得
            letter_title = self.title_input.value
            message_text = self.message_input.value
            
            # --- PDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            
            # フォントファイルの場所を指定して登録
            font_path = os.path.join("font", "AkazukiPOP.ttf")
            pdfmetrics.registerFont(TTFont('Akazukin', font_path))
            
            # A4用紙の余白設定
            doc = SimpleDocTemplate(
                pdf_buffer, 
                pagesize=A4,
                leftMargin=50,
                rightMargin=50,
                topMargin=50,
                bottomMargin=50
            )
            
            styles = getSampleStyleSheet()
            
            # 💡 【新機能】題名用の大きな文字スタイル（中央揃え、24pt）
            title_style = ParagraphStyle(
                name='LetterTitleStyle',
                fontName='Akazukin',
                fontSize=24,
                leading=32,
                textColor='black',
                alignment=1  # 1 は「中央揃え（Center）」に配置する設定です
            )
            
            # 本文用のスタイル（読みやすさ重視）
            letter_style = ParagraphStyle(
                name='LetterStyle',
                fontName='Akazukin',
                fontSize=16,
                leading=22,
                textColor='black'
            )
            
            story = []
            
            # 💡 【新機能】PDFの一番上に題名を配置し、下に30ptのきれいな空間を空けます
            safe_title = letter_title.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe_title, title_style))
            story.append(Spacer(1, 30))  # 題名と本文を区切る空間
            
            # 本文を1行ずつ追加していく処理
            for line in message_text.split('\n'):
                if line.strip() == "":
                    story.append(Spacer(1, 22))
                else:
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, letter_style))
            
            # PDFの組み立て
            doc.build(story)
            
            pdf_buffer.seek(0)
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            # --- PDF作成ここまで ---
            
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


# 安全に起動
bot.run(TOKEN)
