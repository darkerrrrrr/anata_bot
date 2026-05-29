import discord
from discord.ext import commands
from discord import app_commands, ui
import os
import io
import re
import signal
import asyncio
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ----------------------------------------------------
# 1. 準備・設定
# ----------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # メンバー一覧を取得するために必要

bot = commands.Bot(command_prefix="!", intents=intents)

# フォントの登録
font_path = os.path.join("font", "ShipporiMincho-Regular.ttf")
pdfmetrics.registerFont(TTFont("ShipporiMincho", font_path))

# 1行あたりの最大文字数
MAX_CHARS_PER_LINE = 34

def convert_emoji_to_twemoji(text: str) -> str:
    """文章内の絵文字をTwemojiの画像タグに変換する"""
    def replace_emoji(match):
        emoji = match.group(0)
        codepoints = [f"{ord(c):x}" for c in emoji]
        joined_codepoint = "-".join([cp for cp in codepoints if cp != "fe0f"])
        return f'<img src="https://jsdelivr.net{joined_codepoint}.png" width="12" height="12"/>'
    
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u200d\u2600-\u27bf\u2b50]')
    return emoji_pattern.sub(replace_emoji, text)

# ----------------------------------------------------
# 2. 手紙入力用モーダルの定義
# ----------------------------------------------------
class LetterModal(ui.Modal):
    def __init__(self, target_user: discord.User):
        super().__init__(title=f"{target_user.name} への手紙")
        self.target_user = target_user

        self.target_name_input = ui.TextInput(
            label="相手のなまえ（呼び名）",
            placeholder="例：〇〇さん（自動で「へ」が付きます）",
            required=True,
            max_length=20
        )
        self.sender_name_input = ui.TextInput(
            label="あなたのなまえ（※匿名で送る場合は【空欄】のまま）",
            placeholder="例：△△（空欄なら匿名になります）",
            required=False,
            max_length=20
        )
        self.content_input = ui.TextInput(
            label="手紙の中身",
            placeholder="ここにメッセージを入力してください...",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )

        self.add_item(self.target_name_input)
        self.add_item(self.sender_name_input)
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        target_name = self.target_name_input.value.strip()
        sender_name = self.sender_name_input.value.strip()
        content = self.content_input.value

        if not target_name.endswith("へ") and not target_name.endswith("へ "):
            target_name += " へ"
        if sender_name and not sender_name.endswith("より") and not sender_name.endswith("より "):
            sender_name += " より"

        # セーフティロジック：はみ出し計算
        lines = content.split('\n')
        total_calculated_lines = 0

        for line in lines:
            if not line:
                total_calculated_lines += 1
                continue
            
            line_len = len(line)
            actual_lines = (line_len + MAX_CHARS_PER_LINE - 1) // MAX_CHARS_PER_LINE
            total_calculated_lines += max(1, actual_lines)

        if total_calculated_lines > 20:
            over_lines = total_calculated_lines - 20
            await interaction.followup.send(
                f"【便箋からはみ出しています】\n"
                f"手紙が2ページ目に突入してしまいます。1枚に美しく収めるために、"
                f"**あと約 {over_lines} 行分** 文字を削るか、改行を減らしてください。\n"
                f"（現在の計算行数: {total_calculated_lines} / 20行まで）",
                ephemeral=True
            )
            return

        # PDFの生成 (ReportLab)
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(400, 600))

        c.setFillColorRGB(0.98, 0.96, 0.92)
        c.rect(0, 0, 400, 600, fill=True, stroke=False)

        c.setStrokeColorRGB(0.76, 0.72, 0.68)
        c.setLineWidth(0.5)
        start_y = 500
        line_spacing = 24
        for i in range(20):
            y = start_y - (i * line_spacing)
            c.line(40, y, 360, y)

        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle(
            name="LetterStyle",
            fontName="ShipporiMincho",
            fontSize=12,
            leading=24,
            textColor=discord.Color.from_rgb(40, 36, 32),
            alignment=TA_LEFT
        )

        p_target = Paragraph(convert_emoji_to_twemoji(target_name), normal_style)
        p_target.wrap(320, 30)
        p_target.drawOn(c, 40, start_y + 4)

        escaped_content = content.replace('\n', '<br/>')
        html_content = convert_emoji_to_twemoji(escaped_content)
        p_content = Paragraph(html_content, normal_style)
        p_content.wrap(320, 480)
        p_content.drawOn(c, 40, start_y - 480 + 24)

        if sender_name:
            p_sender = Paragraph(convert_emoji_to_twemoji(sender_name), normal_style)
            p_sender.wrap(320, 30)
            approx_width = len(sender_name) * 12
            x_pos = max(40, 360 - approx_width)
            p_sender.drawOn(c, x_pos, start_y - (20 * line_spacing) - 4)

        c.showPage()
        c.save()
        pdf_buffer.seek(0)

        # DM送信処理
        try:
            file = discord.File(pdf_buffer, filename="letter.pdf")
            await self.target_user.send("貴方に、お手紙が届きました。", file=file)
            await interaction.followup.send(f"{self.target_user.name} さんに手紙を無事に届けました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "相手に手紙を届けることができませんでした。\n"
                "（理由：相手がDMを閉鎖している、またはBotをブロックしている可能性があります）",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"送信中に予期せぬエラーが発生しました: {e}", ephemeral=True)

# ----------------------------------------------------
# 3. アプリケーションコマンドの登録
# ----------------------------------------------------
@bot.tree.command(name="貴方に", description="手紙（PDFファイル）を相手のDMに届けます。")
@app_commands.describe(target_username="手紙を届けたい相手の「ユーザー名（@から始まる英数字の名前）」")
async def anata_ni(interaction: discord.Interaction, target_username: str):
    search_name = target_username.strip()
    
    if search_name.startswith("@"):
        search_name = search_name[1:]

    target_user = None
    if interaction.guild:
        target_user = discord.utils.find(lambda m: m.name == search_name, interaction.guild.members)
    
    if not target_user:
        target_user = discord.utils.find(lambda u: u.name == search_name, bot.users)

    if not target_user:
        await interaction.response.send_message(
            f"ユーザー名「{search_name}」が見つかりませんでした。\n"
            "※Botと共通のサーバーに参加しているメンバーの「ユーザー名」を正確に入力してください。", 
            ephemeral=True
        )
        return

    if target_user.bot:
        await interaction.response.send_message("Botに手紙を送ることはできません。", ephemeral=True)
        return

    await interaction.response.send_modal(LetterModal(target_user))

# ----------------------------------------------------
# 4. Bot起動と終了のライフサイクル管理
# ----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!purge"):
        if message.guild and (message.author.guild_permissions.manage_messages or message.author.id == bot.owner_id):
            deleted = 0
            async for msg in message.channel.history(limit=100):
                if msg.author == bot.user:
                    try:
                        await msg.delete()
                        deleted += 1
                    except discord.HTTPException:
                        pass
            await message.channel.send(f"Botのメッセージを {deleted} 件削除しました。", delete_after=5)
        elif not message.guild:
            await message.channel.send("DM内ではこのコマンドを実行できません。")
        else:
            await message.channel.send("このコマンドを実行する権限がありません。", delete_after=5)

async def shutdown(loop, signal_obj=None):
    if signal_obj:
        print(f"終了シグナル ({signal_obj.name}) を受信しました。安全にシャットダウンします...")
    else:
        print("シャットダウンを開始します...")
        
    await bot.close()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

def setup_signal_handlers(loop):
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(loop, s)))
        except NotImplementedError:
            pass

# ----------------------------------------------------
# 5. 実行エントリーポイント
# ----------------------------------------------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    setup_signal_handlers(loop)
    
    try:
        # ステータス変更のコードを除去し、通常のオンライン起動（緑丸）に直しました
        loop.run_until_complete(bot.start(TOKEN))
    except KeyboardInterrupt:
        print("Ctrl+C を検知しました。終了処理を行います...")
        loop.run_until_complete(shutdown(loop))
    finally:
        loop.close()
        print("Botが完全に停止しました。")
