import os
import io
import re
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

# --- 📝 PDFの背景に「便箋の罫線」を描画する関数（全20行固定） ---
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

# --- 👑 絵文字をTwemojiの画像タグに変換する関数 ---
def convert_emojis_to_images(text):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u200d\u2600-\u27bf]+')
    
    def replace_with_img(match):
        emoji = match.group(0)
        codepoints = [f"{ord(c):x}" for c in emoji if ord(c) != 0xfe0f]
        if not codepoints:
            return emoji
        codepoint_str = "-".join(codepoints)
        return f'<img src="https://jsdelivr.net{codepoint_str}.png" width="16" height="16" valign="middle"/>'
    
    return emoji_pattern.sub(replace_with_img, text)

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
        label="手紙の中身",
        style=discord.TextStyle.long,
        placeholder="ここに伝えたい想いを入力してください...",
        required=True,
        max_length=450 
    )

    def __init__(self, target_user: discord.User):
        super().__init__()
        self.target_user = target_user

    async def on_submit(self, interaction: discord.Interaction):
        # タイムアウトを防ぐため即座に保留(defer)を行います
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

            # --- 📐 2ページ目へのはみ出しのみを検知するセーフティロジック ---
            MAX_CHARS_PER_LINE = 34
            total_lines = 0
            
            total_lines += 2 # 宛名分
            
            for line in message_text.split('\n'):
                if line.strip() == "":
                    total_lines += 1
                else:
                    line_len = len(line)
                    lines_needed = (line_len + MAX_CHARS_PER_LINE - 1) // MAX_CHARS_PER_LINE
                    total_lines += lines_needed
                    
            if has_sender:
                total_lines += 2 # 差出人名分

            # 純粋に1ページ（20行）を超えて文字が消えてしまう時だけエラーを出します
            TARGET_LINES = 20
            if total_lines > TARGET_LINES:
                diff = total_lines - TARGET_LINES
                await interaction.followup.send(
                    f"【便箋からはみ出しています】手紙が2ページ目に突入してしまいます。1枚に美しく収めるために、**あと約 {diff} 行分** 文章を削ってください。（現在の合計: {total_lines}/20行）", 
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
            
            # 宛名配置
            story.append(Paragraph(convert_emojis_to_images(target_name), name_style))
            story.append(Spacer(1, 24))
            
            # 本文配置
            for line in message_text.split('\n'):
                if line.strip() == "":
                    story.append(Spacer(1, 24))
                else:
                    story.append(Paragraph(convert_emojis_to_images(line), letter_style))
                    
            # 差出人配置
            if has_sender:
                story.append(Spacer(1, 24))
                story.append(Paragraph(convert_emojis_to_images(sender_name), right_style))
                
            doc.build(story, onFirstPage=draw_letter_lines, onLaterPages=draw_letter_lines)
            pdf_buffer.seek(0)
            
            discord_file = discord.File(pdf_buffer, filename="想い.pdf")
            
            # 💡【修正点】contentの先頭にあった {self.target_user.mention} を完全に削除しました
            await self.target_user.send(
                content="📩 あなたへの想いが届いています。PDFファイルを開いて読んでください。",
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
