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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd)
    print(f"ログインしました: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"スラッシュコマンドを自動同期しました。 ({len(synced)}個のコマンド)")
    except Exception as e:
        print(f"コマンドの自動同期中にエラーが発生しました: {e}")

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

@bot.command(name="sync")
@commands.is_owner()
async def sync_commands(ctx):
    await bot.tree.sync()
    await ctx.send("スラッシュコマンドの手動同期が完了しました！", delete_after=5)

# --- 📝 PDFの背景に「便箋の罫線」を描画する関数（全20行） ---
def draw_letter_lines(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setStrokeColorRGB(0.75, 0.72, 0.68)
    canvas_obj.setLineWidth(0.5)
    
    page_width, page_height = doc.pagesize
    
    # 24pt間隔で、全20行の罫線を引きます（文字の底辺に完全同期）
    start_y = 486
    line_interval = 24
    
    for i in range(20):
        current_y = start_y - (i * line_interval)
        canvas_obj.line(50, current_y, page_width - 50, current_y)
        
    canvas_obj.restoreState()

# --- 📄 モーダルウィンドウ（入力フォーム）の定義 ---
class MessageModal(discord.ui.Modal, title="貴方の想いを伝える手紙"):
    name_input = discord.ui.TextInput(
        label="相手のなまえ（呼び名）",
        style=discord.TextStyle.short,
        placeholder="例：〇〇へ、〇〇さんへ など",
        required=True,
        max_length=50
    )
    sender_input = discord.ui.TextInput(
        label="あなたのなまえ（※匿名で送る場合は【空欄】のまま）",
        style=discord.TextStyle.short,
        placeholder="名前を出して想いを届けたい時だけ、ここに名前を書いてください",
        required=False,
        max_length=50
    )
    message_input = discord.ui.TextInput(
        label="手紙の中身（※便箋がピッタリ文字で埋まるように書いてください）",
        style=discord.TextStyle.long,
        placeholder="便箋の最後まで（約17〜18行分）想いをぎっしり入力してください...",
        required=True,
        max_length=1000
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        # 💡 【タイムアウトバグ修正】送信されたら最優先で即座に保留(defer)を行い、Discordの切断を防ぎます
        await interaction.response.defer(ephemeral=True)
        
        try:
            target_name = self.name_input.value
            message_text = self.message_input.value
            sender_name = self.sender_input.value.strip()
            
            has_sender = (sender_name != "")
            
            if not (target_name.endswith("へ") or target_name.endswith("さん") or target_name.endswith("くん") or target_name.endswith("ちゃん")):
                target_name = f"{target_name} へ"

            if has_sender and not (sender_name.endswith("より") or sender_name.endswith("から")):
                sender_name = f"{sender_name} より"

            # --- 📐 行数の自動計算ロジック ---
            MAX_CHARS_PER_LINE = 34
            total_lines = 0
            
            # 1. 宛名：2行（宛名本体 + 空白スペース）
            total_lines += 2
            
            # 2. 本文の行数を計算
            for line in message_text.split('\n'):
                if line.strip() == "":
                    total_lines += 1
                else:
                    line_len = len(line)
                    lines_needed = (line_len + MAX_CHARS_PER_LINE - 1) // MAX_CHARS_PER_LINE
                    total_lines += lines_needed
                    
            # 3. 差出人名：2行（空白スペース + 名前本体）
            if has_sender:
                total_lines += 2

            # 💡 【チェック】全20行ぴったりになっているか
            TARGET_LINES = 20
            if total_lines != TARGET_LINES:
                diff = TARGET_LINES - total_lines
                if diff > 0:
                    await interaction.followup.send(
                        f"【便箋に余白があります】手紙の下部がスカスカになってしまいます。便箋をぴったり埋めるために、**あと約 {diff} 行分** 文章を書き足してください。（現在の合計: {total_lines}/20行）", 
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"【便箋からはみ出しています】1枚に収まりきりません。きれいに収めるために、**あと約 {abs(diff)} 行分** 文章を削ってください。（現在の合計: {total_lines}/20行）", 
                        ephemeral=True
                    )
                return

            # --- PDFを作成する処理 ---
            pdf_buffer = io.BytesIO()
            font_path = os.path.join("font", "ShipporiMincho-Regular.ttf")
            pdfmetrics.registerFont(TTFont('ShipporiMincho', font_path))
            
            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=landscape(A4),
                leftMargin=50,
                rightMargin=50,
                topMargin=36,
                bottomMargin=50
            )
            
            styles = getSampleStyleSheet()
            name_style = ParagraphStyle(
                name='LetterNameStyle', fontName='ShipporiMincho', fontSize=16, leading=24, textColor='black', alignment=0
            )
            letter_style = ParagraphStyle(
                name='LetterStyle', fontName='ShipporiMincho', fontSize=16, leading=24, textColor='black'
            )
            right_style = ParagraphStyle(
                name='LetterRightStyle', fontName='ShipporiMincho', fontSize=14, leading=24, textColor='black', alignment=2
            )
            
            story = []
            
            # 宛名配置（2行分消費）
            safe_name = target_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(safe_name, name_style))
            story.append(Spacer(1, 24))
            
            # 本文配置
            for line in message_text.split('\n'):
                if line.strip() == "":
                    story.append(Spacer(1, 24))
                else:
                    safe_line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_line, letter_style))
                    
            # 差出人配置（2行分消費）
            if has_sender:
                story.append(Spacer(1, 24))
                safe_sender = sender_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_sender, right_style))
                
            doc.build(story, onFirstPage=draw_letter_lines, onLaterPages=draw_letter_lines)
            pdf_buffer.seek(0)
            
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            
            await self.target_user.send(
                content=f"{self.target_user.mention}\n📩 あなたへの想いが届いています。PDFファイルを開いて読んでください。",
                file=discord_file
            )
            await interaction.followup.send("想いをPDFファイルにして届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("相手のDMが閉じられているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            print(f"PDF作成エラー: {e}")
            await interaction.followup.send(f"送信中にエラーが発生しました。理由: {e}", ephemeral=True)

# --- 💬 スラッシュコマンドの設定 ---
@bot.tree.command(name="貴方に", description="手紙（PDFファイル）を相手のDMに届けます")
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
