import os
import discord
from discord import app_commands
from discord.ext import commands
import io
import asyncio

# 【メッセージ入力画面（ポップアップ）】
class LetterModal(discord.ui.Modal):
    def __init__(self, is_anonymous: bool):
        self.is_anonymous = is_anonymous
        title_text = '送信設定：匿名（名前を隠す）' if is_anonymous else '送信設定：通常（名前を出す）'
        super().__init__(title=title_text)

    # 届ける相手のユーザー名を入力する欄
    target_username = discord.ui.TextInput(
        label='送信相手のユーザー名', 
        placeholder='例: discord_user（@は不要）',
        max_length=32
    )
    
    # メッセージ本文を入力する欄
    letter_content = discord.ui.TextInput(
        label='メッセージ本文', 
        style=discord.TextStyle.long, 
        placeholder='送信したい文章を入力してください...',
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        for guild in interaction.client.guilds:
            member = guild.get_member_named(input_name)
            if member:
                target_user = member
                break

        if not target_user:
            await interaction.followup.send(
                f"エラー：「{input_name}」というユーザーが見つかりませんでした。\n"
                "※Botと同じサーバーに所属しているユーザーのみ検索可能です。", 
                ephemeral=True
            )
            return

        try:
            if self.is_anonymous:
                chat_message = "【匿名メッセージが届きました】"
                letter_title = "あなたへ、大切な想いが届いています"
            else:
                chat_message = f"【{interaction.user.name} さんからのメッセージが届きました】"
                letter_title = f"{interaction.user.name} さんより、大切な想いが届いています"
                
            # 💡 改行をブラウザで正しく表示するために、文章内の改行コードを「<br>」に変換します
            formatted_content = self.letter_content.value.replace("\n", "<br>")

            # 🛠️ 【新機能】無機質に広がらない、中央に収まる美しいHTML手紙のデザイン
            html_template = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Letter</title>
    <style>
        body {{
            background-color: #f4f1ea; /* 優しい薄ベージュ色の背景 */
            font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }}
        .card {{
            background: #ffffff;
            max-width: 500px; /* 💡 文字が横に広がらないように横幅を制限 */
            width: 100%;
            padding: 40px; /* 💡 上下左右にたっぷり余白をとって中央に寄せます */
            box-shadow: 0 4px 15px rgba(0,0,0,0.05); /* ほんのり上品な影 */
            border-radius: 8px;
            box-sizing: border-box;
        }}
        .title {{
            font-size: 16px;
            font-weight: bold;
            color: #555555;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 15px;
            margin-bottom: 25px;
            text-align: center;
        }}
        .content {{
            font-size: 15px;
            line-height: 1.8; /* 行間を広げて読みやすくします */
            color: #333333;
            white-space: normal;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="title">{letter_title}</div>
        <div class="content">{formatted_content}</div>
    </div>
</body>
</html>"""
            
            # メモリー上にHTMLファイル（.html）を作成
            file_data = io.BytesIO(html_template.encode('utf-8'))
            # 💡 拡張子を「.html」に変更して添付します
            discord_file = discord.File(fp=file_data, filename="letter.html")
            
            # 相手のDMに、案内メッセージとファイルを一緒に送信する
            await target_user.send(content=chat_message, file=discord_file)
            
            # 送信した本人に完了報告
            await interaction.followup.send(f"送信完了：{target_user.name} さんのDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("エラー：相手がDMを受信できない設定にしているため、送信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"予期せぬエラーが発生しました: {e}", ephemeral=True)


# 【送信方法を選ぶボタン】
class SelectModeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="匿名（名前を隠して送信）", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="通常（名前を出して送信）", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))


# ─── Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          
        intents.message_content = True  
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


# 🚀 /send コマンドの登録
@bot.tree.command(name="send", description="指定したユーザーのDMにメッセージカード（HTML）を送信します")
async def send_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )


# 🛠️ !msgdel テキストコマンドの登録（変身・自爆システム）
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """過去ログからこのBotのメッセージを全消去し、打たれたコマンドの文字自体を5秒で自爆させます"""
    
    # 過去ログからBot自身のメッセージをすべて無言で削除する処理
    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user and message.id != ctx.message.id:
            try:
                await message.delete()
            except discord.DiscordException:
                pass

    # あなたの打った「!msgdel」をお掃除メッセージに上書き（変身）させます
    try:
        await ctx.message.edit(content="🧹 お掃除が完了しました。このメッセージは5秒後に自動消滅します。")
        await asyncio.sleep(5)
        await ctx.message.delete()
    except discord.DiscordException:
        pass


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")

# 【GitHub用設定】環境変数 DISCORD_TOKEN からトークンを読み込む
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー：環境変数 DISCORD_TOKEN が設定されていません。")
