import os
import discord
from discord import app_commands
from discord.ext import commands
import io

# ─── 1. 画面表示に使う部品（クラス）の定義 ───

# 【メッセージ入力画面（ポップアップ）】
class LetterModal(discord.ui.Modal):
    def __init__(self, is_anonymous: bool):
        self.is_anonymous = is_anonymous
        # 💡 モード名のみをシンプルに表示
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

    # 送信ボタンが押された時の処理
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        input_name = self.target_username.value.strip().lstrip('@')
        target_user = None

        # Botが参加しているすべてのサーバーのメンバーから、ユーザー名が一致する人を探す
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
            # 💡 相手への通知も「匿名」か「誰からか」だけが1秒で伝わる形に変更
            if self.is_anonymous:
                chat_message = "【匿名メッセージが届きました】"
            else:
                chat_message = f"【{interaction.user.name} さんからのメッセージが届きました】"
                
            pure_content = self.letter_content.value
            
            # メモリー上にテキストファイル（.txt）を作成
            file_data = io.BytesIO(pure_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="letter.txt")
            
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

    # 💡 選択肢を無駄のない実用的なテキストに変更
    @discord.ui.button(label="匿名（名前を隠して送信）", style=discord.ButtonStyle.primary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=True))

    @discord.ui.button(label="通常（名前を出して送信）", style=discord.ButtonStyle.success)
    async def name_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LetterModal(is_anonymous=False))


# ─── 2. Botの本体設定 ───
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # メンバー検索
        intents.message_content = True  # !msgdel テキストコマンドを読み取るためON
        
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()


# 🚀 /send コマンドの登録
@bot.tree.command(name="send", description="指定したユーザーのDMにテキストファイルを送信します")
async def send_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        "送信モードを選択してください：", 
        view=SelectModeView(), 
        ephemeral=True
    )


# 🛠️ !msgdel テキストコマンドの登録
@bot.command(name="msgdel")
async def msgdel_command(ctx, limit: int = 20):
    """過去ログからこのBotのメッセージだけを無言で全消去します"""
    try:
        await ctx.message.delete()
    except discord.DiscordException:
        pass

    async for message in ctx.channel.history(limit=limit):
        if message.author == bot.user:
            try:
                await message.delete()
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
