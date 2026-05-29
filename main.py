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
bot = commands.Bot(command_list=["!"], intents=intents)

# フォントの登録
font_path = os.path.join("font", "ShipporiMincho-Regular.ttf")
pdfmetrics.registerFont(TTFont("ShipporiMincho", font_path))

# 1行あたりの最大文字数
MAX_CHARS_PER_LINE = 34

def convert_emoji_to_twemoji(text: str) -> str:
    """文章内の絵文字をTwemojiの画像タグに変換する"""
    def replace_emoji(match):
        emoji = match.group(0)
        # サロゲートペアを考慮してコードポイントを取得
        codepoints = [f"{ord(c):x}" for c in emoji]
        # 異体字セレクタ（fe0f）を除去して結合
        joined_codepoint = "-".join([cp for cp in codepoints if cp != "fe0f"])
        return f'<img src="https://jsdelivr.net{joined_codepoint}.png" width="12" height="12"/>'
    
    # 一般的な絵文字の正規表現（必要に応じて拡張可能）
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
        # 処理中であることをDiscordに伝える（タイムアウト防止、タイムラインには非表示）
        await interaction.response.defer(ephemeral=True)

        target_name = self.target_name_input.value.strip()
        sender_name = self.sender_name_input.value.strip()
        content = self.content_input.value

        # 名前の末尾自動補正
        if not target_name.endswith("へ") and not target_name.endswith("へ "):
            target_name += " へ"
        if sender_name and not sender_name.endswith("より") and not sender_name.endswith("より "):
            sender_name += " より"

        # ----------------------------------------------------
        # セーフティロジック：はみ出し計算
        # ----------------------------------------------------
        lines = content.split('\n')
        total_calculated_lines = 0

        for line in lines:
            if not line:
                total_calculated_lines += 1
                continue
            
            # 文字列の長さを計算（簡易版。絵文字や半角全角を厳密にやる場合は要調整）
            line_len = len(line)
            actual_lines = (line_len + MAX_CHARS_PER_LINE - 1) // MAX_CHARS_PER_LINE
            total_calculated_lines += max(1, actual_lines)

        # 1ページ（20行）制限をオーバーしている場合の警告処理
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

        # ----------------------------------------------------
        # PDFの生成 (ReportLab)
        # ----------------------------------------------------
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=(400, 600))

        # 背景色（セピア・淡いベージュ調）
        c.setFillColorRGB(0.98, 0.96, 0.92)
        c.rect(0, 0, 400, 600, fill=True, stroke=False)

        # 罫線の描画（24pt間隔、全20行）
        c.setStrokeColorRGB(0.76, 0.72, 0.68)
        c.setLineWidth(0.5)
        start_y = 500
        line_spacing = 24
        for i in range(20):
            y = start_y - (i * line_spacing)
            c.line(40, y, 360, y)

        # テキストのレンダリング設定
        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle(
            name="LetterStyle",
            fontName="ShipporiMincho",
            fontSize=12,
            leading=24,  # 罫線の間隔(24)と完全に一致させる
            textColor=discord.Color.from_rgb(40, 36, 32),
            alignment=TA_LEFT
        )

        # 宛名の描画（最上部の罫線の上に配置）
        p_target = Paragraph(convert_emoji_to_twemoji(target_name), normal_style)
        p_target.wrap(320, 30)
        p_target.drawOn(c, 40, start_y + 4)

        # 本文の描画（1行目の罫線の上から順に流し込む）
        escaped_content = content.replace('\n', '<br/>')
        html_content = convert_emoji_to_twemoji(escaped_content)
        p_content = Paragraph(html_content, normal_style)
        p_content.wrap(320, 480)
        p_content.drawOn(c, 40, start_y - 480 + 24)

        # 差出人の描画（最下部のさらに下に配置、右寄せっぽく見せるためX座標を調整）
        if sender_name:
            p_sender = Paragraph(convert_emoji_to_twemoji(sender_name), normal_style)
            p_sender.wrap(320, 30)
            # 文字数に応じて右端に寄せる（簡易計算）
            approx_width = len(sender_name) * 12
            x_pos = max(40, 360 - approx_width)
            p_sender.drawOn(c, x_pos, start_y - (20 * line_spacing) - 4)

        c.showPage()
        c.save()
        pdf_buffer.seek(0)

        # ----------------------------------------------------
        # DM送信処理
        # ----------------------------------------------------
        try:
            file = discord.File(pdf_buffer, filename="letter.pdf")
            await self.target_user.send("貴方に、お手紙が届きました。", file=file)
            await interaction.followup.send("手紙を無事に届けました。", ephemeral=True)
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
@app_commands.describe(
    target_user="手紙を届けたい相手（ユーザー名を選択してください）"
)
async def anata_ni(interaction: discord.Interaction, target_user: discord.User):
    # Botへの送信はあらかじめブロックする
    if target_user.bot:
        await interaction.response.send_message("Botに手紙を送ることはできません。", ephemeral=True)
        return

    # モーダルを開いてユーザー入力を促す
    await interaction.response.send_modal(LetterModal(target_user))

# ----------------------------------------------------
# 4. Bot起動と終了のライフサイクル管理
# ----------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    try:
        # スラッシュコマンドのグローバル同期
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # 管理用：!purge コマンド（Bot自身の過去メッセージを最大100件消去）
    if message.content.startswith("!purge"):
        if message.author.guild_permissions.manage_messages or message.author.id == bot.owner_id:
            deleted = 0
            async for msg in message.channel.history(limit=100):
                if msg.author == bot.user:
                    try:
                        await msg.delete()
                        deleted += 1
                    except discord.HTTPException:
                        pass
            await message.channel.send(f"Botのメッセージを {deleted} 件削除しました。", delete_after=5)
        else:
            await message.channel.send("このコマンドを実行する権限がありません。", delete_after=5)

async def shutdown(loop, signal_obj=None):
    """終了シグナルを受信した際に安全にシャットダウンする関数"""
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
    """Linux/macOS環境用の終了シグナルハンドラ設定"""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(loop, s)))
        except NotImplementedError:
            # Windows環境では add_signal_handler が使えないため例外を回避
            pass

# ----------------------------------------------------
# 5. 実行エントリーポイント
# ----------------------------------------------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    setup_signal_handlers(loop)
    
    try:
        loop.run_until_complete(bot.start(TOKEN))
    except KeyboardInterrupt:
        # Windows等でCtrl+Cが押された場合のハンドリング
        print("Ctrl+C を検知しました。終了処理を行います...")
        loop.run_until_complete(shutdown(loop))
    finally:
        loop.close()
        print("Botが完全に停止しました。")

