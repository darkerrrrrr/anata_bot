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
intents.message_content = True  # メッセージ内容を読み取る設定
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


# --- 🧹 !purge コマンドの設定（DM画面でも機能する削除機能） ---
@bot.command(name="purge")
async def purge_messages(ctx, limit: int = 100):
    deleted_count = 0
    
    try:
        # DM画面のメッセージ履歴を過去100件分取得してループ処理します
        async for message in ctx.channel.history(limit=limit):
            # メッセージの送信者がこのBot自身だった場合のみ削除します
            if message.author == bot.user:
                await message.delete()
                deleted_count += 1
                
        # 削除が終わったら完了通知を送り、5秒後に自動消去します
        await ctx.send(f"Botのメッセージを {deleted_count} 件削除しました。", delete_after=5)
        
    except discord.Forbidden:
        await ctx.send("メッセージを削除する権限がありませんでした。", delete_after=5)
    except Exception as e:
        await ctx.send(f"削除中にエラーが発生しました: {e}", delete_after=5)


# 安全にトークンを読み込んで起動
bot.run(TOKEN)
